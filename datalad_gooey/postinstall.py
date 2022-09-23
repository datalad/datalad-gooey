from sys import platform

from platformdirs import user_data_path

from .resource_provider import gooey_resources


def perform_post_install_tasks():
    if platform == "linux":
        create_desktop_file()
        copy_icon()
    else:
        print("Nothing to do")


def create_desktop_file():
    df_name = "datalad-gooey.desktop"
    template_path = gooey_resources.get_resource_path('desktop') / df_name
    target_path = user_data_path() / "applications" / df_name

    if not target_path.parent.exists():
        target_path.parent.mkdir()

    target_path.write_text(template_path.read_text())
    print("Created desktop file in", target_path)


def copy_icon():
    source_path = gooey_resources.get_icon_path('datalad_gooey_logo')
    target_path = user_data_path() / "icons" / "datalad-gooey"

    if not target_path.parent.exists():
        target_path.parent.mkdir()

    # svg is text & rewriting file contents is ok, no need for shutil.copy
    target_path.write_text(source_path.read_text())
    print("Created icon in", target_path)
