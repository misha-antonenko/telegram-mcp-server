this document describes an MCP server that allows the LLM to use Telegram as a normal human user.

# functional requirements

the server must use FastMCP and Telethon. the server must support the following functionality:
1. `get_chats`: get a paginated list of chats sorted by the recency of the last message (more recent go earlier).
    - pages are 16 chats long by default.
    - parameter `page_idx` (defaults to 0) specifies the index of the page to fetch.
    - parameter `unread` (defaults to `True`) returns only the chats that have unread messages when `True` and only the chats that don't have unread messages when `False`.
    - parameter `archived` (defaults to `False`) returns only the archived chats when `True` and only unarchived chats when `False`.
    - with each chat, include
        - a preview (≤32 characters) of the last message.
        - whether there are unread messages in the chat.
    - must correctly handle topics within supergroups.
2. `get_messages`: get a paginated list of messages from the given chat sorted by recency.
    - pages are 16 messages long by default.
    - attached images, videos, files, voice or video messages are replaced by their IDs.
    - with every message must come:
        - the timestamp.
        - the parent message, if the given one is a reply.
        - the ID of the message's sender.
        - the ID of the original author of the message, if the message was forwarded.
    - Telegram stickers must be replaced by a XML markers indicating the sticker ID and the alt text (an emoji).
3. `get_image`: fetch the image (caching it in a local directory) by ID.
4. `get_user`: get information about the user by their ID:
    - name.
    - nickname.
    - bio.
    - the ID of the current profile image.
5. `send_message`: send the given Markdown-formatted message to the given chat (specified by ID), applying `telegramify-markdown`.
    - must support image, video, and file attachments.
    - must support specifying a message to reply to.
6. `forward_message`: forward the message with the given ID to the given chat.

the output of each `get_*` method must be valid YAML. use `|` to format strings that are multiline or contain special characters.

# implementation details

1. for each entity (`Chat`, `User`, `Message`) create a Pydantic class with a method `from_telethon`. this class will include only the fields of Telethon entities that must be displayed by the API. define these classes in separate private modules.
2. each `get_*` method converts the corresponding Telethon entities to our Pydantic class. these Pydantic classes are then converted into dictionaries, combined into lists, and serialized into YAML, which is returned to the client of the MCP server. define (in a separate module) a special decorator that would take a function's return value and serialize it into YAML, handling multiline and needing-escaping strings properly.
3. use `pydantic-settings` to manage configuration. load it from dotenv or YAML files.
4. use `uv`.

# tests

use `pytest` and mocking to test each method comprehensively.
