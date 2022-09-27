from notion_client import Client
import logging
import markdownify

notion: Client
root_page_id: str
notion_enabled = True
page_ids = {}


def init_notion(config):
    global notion, root_page_id, notion_enabled
    root_page_id = config['notion_root_page_id']
    notion_enabled = config['notion_enabled']
    if not notion_enabled:
        return
    notion = Client(auth=config['notion_token'], log_level=logging.DEBUG)


def create_page(title, content="", path=None):
    if content:
        content = markdownify.markdownify(content)
    if not notion_enabled:
        return
    if title is None:
        title = "Untitled"
    path = clean_path(path)
    parent_id = get_parent_page_id(path)
    page = notion.pages.create(**{
        "parent": {
            "page_id": parent_id
        },
        "properties": {
            "title": {
                "title": [
                    {
                        "type": "text",
                        "text": {
                            "content": title
                        }
                    }
                ]
            }
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": content
                            }
                        }
                    ]
                }
            }
        ]
    })
    page_ids[path] = page["id"]


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
            title = pages[i] if pages[i] != 0 else "Untitled"
            create_page(title, "", page_path)

    return page_ids["/".join(pages)]


def clean_path(path):
    return "/".join(list(filter(None, path.split("/"))))
