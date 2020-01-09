import os
import random
import re
import string
import time
import uuid
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

import flask
import msal
import yaml
from pathvalidate import sanitize_filename
from requests_oauthlib import OAuth2Session

output_path = Path('output')
graph_url = 'https://graph.microsoft.com/v1.0'
authority_url = 'https://login.microsoftonline.com/common'
scopes = ['Notes.Read', 'Notes.Read.All']
redirect_uri = 'http://localhost:5000/getToken'

app = flask.Flask(__name__)
app.debug = True
app.secret_key = os.urandom(16)

with open('config.yaml') as f:
    config = yaml.safe_load(f)

application = msal.ConfidentialClientApplication(
    config['client_id'],
    authority=authority_url,
    client_credential=config['secret']
)


@app.route("/")
def main():
    resp = flask.Response(status=307)
    resp.headers['location'] = '/login'
    return resp


@app.route("/login")
def login():
    auth_state = str(uuid.uuid4())
    flask.session['state'] = auth_state
    authorization_url = application.get_authorization_request_url(scopes, state=auth_state,
                                                                  redirect_uri=redirect_uri)
    resp = flask.Response(status=307)
    resp.headers['location'] = authorization_url
    return resp


def get_json(graph_client, url, params=None):
    values = []
    next_page = url
    while next_page:
        resp = get(graph_client, next_page, params=params).json()
        if 'value' not in resp:
            raise RuntimeError(f'Invalid server response: {resp}')
        values += resp['value']
        next_page = resp.get('@odata.nextLink')
    return values


def get(graph_client, url, params=None):
    while True:
        resp = graph_client.get(url, params=params)
        if resp.status_code == 429:
            # We are being throttled due to too many requests.
            # See https://docs.microsoft.com/en-us/graph/throttling
            print('        Too many requests, waiting 20s and trying again.')
            time.sleep(20)
        elif resp.status_code == 500:
            # In my case, one specific note page consistently gave this status
            # code when trying to get the content. The error was "19999:
            # Something failed, the API cannot share any more information
            # at the time of the request."
            print('        Error 500, skipping this page.')
            return None
        else:
            resp.raise_for_status()
            return resp


def download_attachments(graph_client, content, out_dir):
    image_dir = out_dir / 'images'
    attachment_dir = out_dir / 'attachments'

    class MyHTMLParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            self.attrs = {k: v for k, v in attrs}

    def generate_html(tag, props):
        element = ElementTree.Element(tag, attrib=props)
        return ElementTree.tostring(element, encoding='unicode')

    def download_image(tag_match):
        # <img width="843" height="218.5" src="..." data-src-type="image/png" data-fullres-src="..."
        # data-fullres-src-type="image/png" />
        parser = MyHTMLParser()
        parser.feed(tag_match[0])
        props = parser.attrs
        image_url = props.get('data-fullres-src', props['src'])
        image_type = props.get('data-fullres-src-type', props['data-src-type']).split("/")[-1]
        file_name = ''.join(random.choice(string.ascii_lowercase) for _ in range(10)) + '.' + image_type
        img = get(graph_client, image_url).content
        print(f'      Downloaded image of {len(img)} bytes.')
        image_dir.mkdir(exist_ok=True)
        with open(image_dir / file_name, "wb") as f:
            f.write(img)
        props['src'] = "images/" + file_name
        props = {k: v for k, v in props.items() if 'data-fullres-src' not in k}
        return generate_html('img', props)

    def download_attachment(tag_match):
        # <object data-attachment="Trig_Cheat_Sheet.pdf" type="application/pdf" data="..."
        # style="position:absolute;left:528px;top:139px" />
        parser = MyHTMLParser()
        parser.feed(tag_match[0])
        props = parser.attrs
        data_url = props['data']
        file_name = props['data-attachment']
        if (attachment_dir / file_name).exists():
            print(f'      Attachment {file_name} already downloaded; skipping.')
        else:
            data = get(graph_client, data_url).content
            print(f'      Downloaded attachment {file_name} of {len(data)} bytes.')
            attachment_dir.mkdir(exist_ok=True)
            with open(attachment_dir / file_name, "wb") as f:
                f.write(data)
        props['data'] = "attachments/" + file_name
        return generate_html('object', props)

    content = re.sub(r"<img .*?\/>", download_image, content, flags=re.DOTALL)
    content = re.sub(r"<object .*?\/>", download_attachment, content, flags=re.DOTALL)
    return content


@app.route("/getToken")
def main_logic():
    code = flask.request.args['code']

    token = application.acquire_token_by_authorization_code(code, scopes=scopes,
                                                            redirect_uri=redirect_uri)
    graph_client = OAuth2Session(token=token)

    notebooks = get_json(graph_client, f'{graph_url}/me/onenote/notebooks')
    print(f'Got {len(notebooks)} notebooks.')
    for nb in notebooks:
        nb_name = nb["displayName"]
        print(f'Opening notebook {nb_name}')
        sections = get_json(graph_client, nb['sectionsUrl'])
        print(f'  Got {len(sections)} sections.')
        for sec in sections:
            sec_name = sec["displayName"]
            print(f'  Opening section {sec_name}')
            pages = get_json(graph_client, sec['pagesUrl'] + '?pagelevel=true')
            print(f'    Got {len(pages)} pages.')
            pages = sorted([(page['order'], page) for page in pages])
            level_dirs = [None]*4
            for order, page in pages:
                level = page['level']
                page_title = sanitize_filename(f'{order}_{page["title"]}', platform='auto')
                print(f'    Opening page {page_title}')
                if level == 0:
                    out_dir = output_path / nb_name / sec_name / page_title
                else:
                    out_dir = level_dirs[level - 1] / page_title
                level_dirs[level] = out_dir
                out_html = out_dir / 'main.html'
                if out_html.exists():
                    print('      HTML file already exists; skipping this page')
                    continue
                out_dir.mkdir(parents=True, exist_ok=True)
                response = get(graph_client, page['contentUrl'])
                if response is not None:
                    content = response.text
                    print(f'      Got content of length {len(content)}')
                    content = download_attachments(graph_client, content, out_dir)
                    with open(out_html, "w") as f:
                        f.write(content)

    print("Done!")
    return flask.render_template_string('<html>'
                                        '<head><title>Done</title></head>'
                                        '<body><p1><b>Done</b></p1></body>'
                                        '</html>')


if __name__ == "__main__":
    app.run()
