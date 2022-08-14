"""
Author:
    chuanqi.tan ### gmail ### com
"""
import os
import shutil
import fire


def move_and_rename(path, main_file):
    print(path, main_file)

    last_dir = path.split("/")[-1]
    old_path = "{}/main.html".format(path)
    new_path = "{}.html".format(path)

    img_path = "{}/images".format(path)
    new_img_dir = os.path.dirname(new_path) + "/images"

    shutil.move(old_path, new_path)

    if os.path.exists(img_path):
        if not os.path.exists(new_img_dir):
            os.mkdir(new_img_dir)

        for jpg in os.listdir(img_path):
            old_jpg_path = "{}/{}".format(img_path, jpg)
            new_jpg_path = "{}/{}".format(new_img_dir, jpg)
            shutil.move(old_jpg_path, new_jpg_path)

        if os.path.exists(img_path) and len(os.listdir(img_path)) == 0:
            shutil.rmtree(img_path)

    if os.path.exists(path) and len(os.listdir(path)) == 0:
        shutil.rmtree(path)


def main(target_dir):
    htmls = os.walk(target_dir)
    for path, dir_list, file_list in htmls:
        # print(path, dir_list, file_list)
        for file_name in file_list:
            if file_name == "main.html":
                move_and_rename(path, file_name)


if __name__ == "__main__":
    fire.Fire(main)
