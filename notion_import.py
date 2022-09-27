import re
import time

from md2notion.upload import upload
from notion.block import PageBlock
from notion.client import NotionClient
from urllib3.util import Retry

client: NotionClient
root_page_id: str
notion_enabled = True
page_ids = {}


def init_notion(config):
    global client, root_page_id, notion_enabled
    root_page_id = config['notion_root_page_id']
    notion_enabled = config['notion_enabled']
    if not notion_enabled:
        return
    client = NotionClient(token_v2=config['notion_token'], client_specified_retry=retry(), start_monitoring=True,
                          monitor=True)


def create_page(path, md_file=None):
    if not notion_enabled:
        return
    path = clean_path(path)
    title = path.split("/")[-1]
    title = re.sub(r'^[0-9]\s', '', title)
    if title == "":
        title = "Untitled"

    parent_id = get_parent_page_id(path)
    print("Creating page: " + title + " in " + parent_id)
    parent_page = client.get_block(parent_id)

    page = parent_page.children.add_new(PageBlock, title=title)
    time.sleep(2)
    if md_file:
        print('Uploading', md_file)
        with open(md_file, "r", encoding="utf-8") as f:
            upload(f, page)
        time.sleep(2)
    page_ids[path] = page.id


def get_parent_page_id(path):
    pages = path.split("/")
    if len(pages) <= 1:
        return root_page_id
    pages.pop()
    if path in page_ids:
        return page_ids[path]

    for i in range(len(pages)):
        page_path = "/".join(pages[:i + 1])
        if page_path not in page_ids:
            create_page(page_path)

    return page_ids["/".join(pages)]


def clean_path(path):
    return "/".join(list(filter(None, path.split("/"))))


def retry():
    return Retry(
        5,
        backoff_factor=20,
        status_forcelist=(429,),
        # CAUTION: adding 'POST' to this list which is not technically idempotent
        method_whitelist=(
            "POST",
            "HEAD",
            "TRACE",
            "GET",
            "PUT",
            "OPTIONS",
            "DELETE",
        )
    )
