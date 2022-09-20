from sys import platform

from importlib_resources import files  # from Python 3.10 use importlib.resources
from platformdirs import user_data_path


def perform_post_install_tasks():
    if platform == "linux":
        create_desktop_file()
    else:
        print("Nothing to do")


def create_desktop_file():
    df_name = "datalad-gooey.desktop"
    template_path = files("datalad_gooey.resources.desktop").joinpath(df_name)
    target_path = user_data_path() / "applications" / df_name

    if not target_path.parent.exists():
        target_path.parent.mkdir()

    target_path.write_text(template_path.read_text())
    print("Created desktop file in", target_path)
