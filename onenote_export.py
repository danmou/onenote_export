import os
import random
import re
import string
import time
import uuid
from fnmatch import fnmatch
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

import click
import flask
import msal
import yaml
from pathvalidate import sanitize_filename
from requests_oauthlib import OAuth2Session

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


def get_json(graph_client, url, params=None, indent=0):
    values = []
    next_page = url
    while next_page:
        resp = get(graph_client, next_page, params=params, indent=indent).json()
        if 'value' not in resp:
            raise RuntimeError(f'Invalid server response: {resp}')
        values += resp['value']
        next_page = resp.get('@odata.nextLink')
    return values


def get(graph_client, url, params=None, indent=0):
    while True:
        resp = graph_client.get(url, params=params)
        if resp.status_code == 429:
            # We are being throttled due to too many requests.
            # See https://docs.microsoft.com/en-us/graph/throttling
            indent_print(indent, 'Too many requests, waiting 20s and trying again.')
            time.sleep(20)
        elif resp.status_code == 500:
            # In my case, one specific note page consistently gave this status
            # code when trying to get the content. The error was "19999:
            # Something failed, the API cannot share any more information
            # at the time of the request."
            indent_print(indent, 'Error 500, skipping this page.')
            return None
        elif resp.status_code == 504:
            indent_print(indent, 'Request timed out, probably due to a large attachment. Skipping.')
            return None
        else:
            resp.raise_for_status()
            return resp


def download_attachments(graph_client, content, out_dir, indent=0):
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
        if hasattr(parser, 'attrs'):
            props = parser.attrs
            image_url = props.get('data-fullres-src', props['src'])
            image_type = props.get('data-fullres-src-type', props['data-src-type']).split("/")[-1]
            file_name = ''.join(random.choice(string.ascii_lowercase) for _ in range(10)) + '.' + image_type
            req = get(graph_client, image_url, indent=indent)
            if req is None:
                return tag_match[0]
            img = req.content
            indent_print(indent, f'Downloaded image of {len(img)} bytes.')
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
            indent_print(indent, f'Attachment {file_name} already downloaded; skipping.')
        else:
            req = get(graph_client, data_url, indent=indent)
            if req is None:
                return tag_match[0]
            data = req.content
            indent_print(indent, f'Downloaded attachment {file_name} of {len(data)} bytes.')
            attachment_dir.mkdir(exist_ok=True)
            with open(attachment_dir / file_name, "wb") as f:
                f.write(data)
        props['data'] = "attachments/" + file_name
        return generate_html('object', props)

    content = re.sub(r"<img .*?\/>", download_image, content, flags=re.DOTALL)
    content = re.sub(r"<object .*?\/>", download_attachment, content, flags=re.DOTALL)
    return content


def indent_print(depth, text):
    print('  ' * depth + text)


def filter_items(items, select, name='items', indent=0):
    if not select:
        return items, select
    items = [item for item in items
             if fnmatch(item.get('displayName', item.get('title')).lower(), select[0].lower())]
    if not items:
        indent_print(indent, f'No {name} found matching {select[0]}')
    return items, select[1:]


def download_notebooks(graph_client, path, select=None, indent=0):
    notebooks = get_json(graph_client, f'{graph_url}/me/onenote/notebooks')
    indent_print(0, f'Got {len(notebooks)} notebooks.')
    notebooks, select = filter_items(notebooks, select, 'notebooks', indent)
    for nb in notebooks:
        nb_name = nb["displayName"]
        indent_print(indent, f'Opening notebook {nb_name}')
        sections = get_json(graph_client, nb['sectionsUrl'])
        section_groups = get_json(graph_client, nb['sectionGroupsUrl'])
        indent_print(indent + 1, f'Got {len(sections)} sections and {len(section_groups)} section groups.')
        download_sections(graph_client, sections, path / nb_name, select, indent=indent + 1)
        download_section_groups(graph_client, section_groups, path / nb_name, select, indent=indent + 1)


def download_section_groups(graph_client, section_groups, path, select=None, indent=0):
    section_groups, select = filter_items(section_groups, select, 'section groups', indent)
    for sg in section_groups:
        sg_name = sg["displayName"]
        indent_print(indent, f'Opening section group {sg_name}')
        sections = get_json(graph_client, sg['sectionsUrl'])
        indent_print(indent + 1, f'Got {len(sections)} sections.')
        download_sections(graph_client, sections, path / sg_name, select, indent=indent + 1)


def download_sections(graph_client, sections, path, select=None, indent=0):
    sections, select = filter_items(sections, select, 'sections', indent)
    for sec in sections:
        sec_name = sec["displayName"]
        indent_print(indent, f'Opening section {sec_name}')
        pages = get_json(graph_client, sec['pagesUrl'] + '?pagelevel=true')
        indent_print(indent + 1, f'Got {len(pages)} pages.')
        download_pages(graph_client, pages, path / sec_name, select, indent=indent + 1)


def download_pages(graph_client, pages, path, select=None, indent=0):
    pages, select = filter_items(pages, select, 'pages', indent)
    pages = sorted([(page['order'], page) for page in pages])
    level_dirs = [None] * 4
    for order, page in pages:
        level = page['level']
        page_title = sanitize_filename(f'{order} {page["title"]}', platform='auto')
        indent_print(indent, f'Opening page {page_title}')
        if level == 0:
            page_dir = path / page_title
        else:
            page_dir = level_dirs[level - 1] / page_title
        level_dirs[level] = page_dir
        download_page(graph_client, page['contentUrl'], page_dir, indent=indent + 1)


def download_page(graph_client, page_url, path, indent=0):
    out_html = path / 'main.html'
    if out_html.exists():
        indent_print(indent, 'HTML file already exists; skipping this page')
        return
    path.mkdir(parents=True, exist_ok=True)
    response = get(graph_client, page_url, indent=indent)
    if response is not None:
        content = response.text
        indent_print(indent, f'Got content of length {len(content)}')
        content = download_attachments(graph_client, content, path, indent=indent)
        with open(out_html, "w", encoding='utf-8') as f:
            f.write(content)


@app.route("/getToken")
def main_logic():
    code = flask.request.args['code']
    token = application.acquire_token_by_authorization_code(code, scopes=scopes,
                                                            redirect_uri=redirect_uri)
    graph_client = OAuth2Session(token=token)
    download_notebooks(graph_client, app.config['output_path'], app.config['select_path'], indent=0)
    print("Done!")
    return flask.render_template_string('<html>'
                                        '<head><title>Done</title></head>'
                                        '<body><p1><b>Done</b></p1></body>'
                                        '</html>')


@click.command()
@click.option('-s', '--select', default='',
              help='Only convert a subset of notes, given as a slash-separated path. For example '
                   '`-p mynotebook` or `-p mynotebook/mysection/mynote`. Wildcards are supported: '
                   '`-p mynotebook/*/mynote`.')
@click.option('-o', '--outdir', default='output', help='Path to output directory.')
def main_command(select, outdir):
    app.config['select_path'] = [x for x in select.split('/') if x]
    app.config['output_path'] = Path(outdir)
    app.run()


if __name__ == "__main__":
    main_command()
