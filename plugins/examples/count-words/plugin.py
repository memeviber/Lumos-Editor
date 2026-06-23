def count_words_in_file():
    text = lumos.get_editor_text()  # type: ignore
    word_count = len(text.split())
    lumos.show_message("Word Count", f"Word Count: {word_count}")  # type: ignore


lumos.plugin_manager.add_menu_action(  # type: ignore
    menu_name="Tools",
    text="Count Words in File",
    callback=count_words_in_file,
    shortcut="Ctrl+Alt+W",
)
