import sys
from asyncio import create_subprocess_shell, sleep, subprocess
from io import BytesIO, StringIO
from time import gmtime, strftime, time
from traceback import format_exc

from pyrogram.errors import (ChannelInvalid, ChannelPrivate, ChatAdminRequired,
                             EntityBoundsInvalid, FloodWait, MessageTooLong,
                             PeerIdInvalid, RPCError)
from pyrogram.types import Message

from Powers import BOT_TOKEN, LOGFILE, LOGGER, MESSAGE_DUMP, UPTIME, OWNER_ID, defult_dev, OWNER_ID
from Powers.bot_class import Gojo
from Powers.database.chats_db import Chats
from Powers.utils.clean_file import remove_markdown_and_html
from Powers.utils.custom_filters import command
from Powers.utils.http_helper import *
from Powers.utils.parser import mention_markdown

@Gojo.on_message(command("adddev"))
async def add_dev(c: Gojo, m:Message):
  if m.from_user.id != OWNER_ID:
    await m.reply_text("Only owner can do that")
    return
  split = m.text.split(None)
  reply_to = m.reply_to_message
  if len(split) != 2 or not reply_to:
    await m.reply_text("Give me an id or reply to message to add the user in dev")
    return
  if reply_to:
    user = reply_to.from_user.id
  elif len(split) == 2:
    try:
      user = int(split[1])
    except ValueError:
      await m.reply_text("Give me id of the user")
      return
  defult_dev.append(user)
  return
      
@Gojo.on_message(command("ping", sudo_cmd=True))
async def ping(_, m: Message):
    LOGGER.info(f"{m.from_user.id} used ping cmd in {m.chat.id}")
    start = time()
    replymsg = await m.reply_text(text="Pinging...", quote=True)
    delta_ping = time() - start
    await replymsg.edit_text(f"<b>Pong!</b>\n{delta_ping * 1000:.3f} ms")
    return


@Gojo.on_message(command("logs", dev_cmd=True))
async def send_log(c: Gojo, m: Message):
    replymsg = await m.reply_text("Sending logs...!")
    await c.send_message(
        MESSAGE_DUMP,
        f"#LOGS\n\n**User:** {(await mention_markdown(m.from_user.first_name, m.from_user.id))}",
    )
    # Send logs
    with open(LOGFILE) as f:
        raw = ((f.read()))[1]
    await m.reply_document(
        document=LOGFILE,
        quote=True,
    )
    await replymsg.delete()
    return


@Gojo.on_message(command("neofetch", dev_cmd=True))
async def neofetch_stats(_, m: Message):
    cmd = "neofetch --stdout"

    process = await create_subprocess_shell(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    e = stderr.decode()
    if not e:
        e = "No Error"
    OUTPUT = stdout.decode()
    if not OUTPUT:
        OUTPUT = "No Output"

    try:
        await m.reply_text(OUTPUT, quote=True)
    except MessageTooLong:
        with BytesIO(str.encode(await remove_markdown_and_html(OUTPUT))) as f:
            f.name = "neofetch.txt"
            await m.reply_document(document=f, caption="neofetch result")
        await m.delete()
    return


@Gojo.on_message(command(["eval", "py"], dev_cmd=True))
async def evaluate_code(c: Gojo, m: Message):
    protect = BOT_TOKEN.split(":")
    initial = protect[0]
    end = protect[1][-5:]
    if len(m.text.split()) == 1:
        await m.reply_text(text="Please execute the code correctly!")
        return
    sm = await m.reply_text("`Processing...`")
    cmd = m.text.split(None, maxsplit=1)[1]

    reply_to_id = m.id
    if m.reply_to_message:
        reply_to_id = m.reply_to_message.id

    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = sys.stdout = StringIO()
    redirected_error = sys.stderr = StringIO()
    stdout, stderr, exc = None, None, None

    try:
        await aexec(cmd, c, m)
    except Exception as ef:
        LOGGER.error(ef)
        exc = format_exc()

    stdout = redirected_output.getvalue()
    stderr = redirected_error.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr

    evaluation = ""
    if exc:
        evaluation = exc
    elif stderr:
        evaluation = stderr
    elif stdout:
        evaluation = stdout
    else:
        evaluation = "Success"
    evaluation = evaluation.strip()
    if (
        (evaluation.startswith(initial) or evaluation.endswith(end))
        or (BOT_TOKEN in evaluation)
    ) and m.from_user.id != OWNER_ID:
        evaluation = "Bhaag ja bsdk bada aya token nikalne wala"
        await c.send_message(
            MESSAGE_DUMP,
            f"@{m.from_user.username} TREID TO FETCH ENV OF BOT \n userid = {m.from_user.id}",
        )
    final_output = f"<b>EVAL</b>: <code>{cmd}</code>\n\n<b>OUTPUT</b>:\n<code>{evaluation}</code> \n"

    try:
        await sm.edit(final_output)
    except MessageTooLong:
        with BytesIO(str.encode(await remove_markdown_and_html(final_output))) as f:
            f.name = "py.txt"
            await m.reply_document(
                document=f,
                caption=cmd,
                disable_notification=True,
                reply_to_message_id=reply_to_id,
            )
        await sm.delete()

    return


async def aexec(code, c, m):
    exec("async def __aexec(c, m): " + "".join(f"\n {l}" for l in code.split("\n")))
    return await locals()["__aexec"](c, m)


HARMFUL = [
    "base64",
    "bash",
    "get_me()",
    "phone",
    "os.system",
    "sys.stdout",
    "sys.stderr",
    "subprocess",
    "DB_URI",
    "DB_URI",
    "BOT_TOKEN",
    "API_HASH",
    "APP_ID",
]


@Gojo.on_message(command(["exec", "sh"], dev_cmd=True))
async def execution(c: Gojo, m: Message):
    protect = BOT_TOKEN.split(":")
    initial = protect[0]
    end = protect[1][-5:]
    if len(m.text.split()) == 1:
        await m.reply_text(text="Please execute the code correctly!")
        return
    sm = await m.reply_text("`Processing...`\n")
    cmd = m.text.split(maxsplit=1)[1]

    reply_to_id = m.id
    if m.reply_to_message:
        reply_to_id = m.reply_to_message.id

    process = await create_subprocess_shell(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    e = stderr.decode().strip()
    if not e:
        e = "No Error"
    o = stdout.decode().strip()
    if not o:
        o = "No Output"
    out = o
    xxx = o.split()
    for OwO in xxx:
      if OwO.startswith(initial) or OwO.endswith(end):
          out = "You can't access them"
          break
    for x in xxx:
        xx = x.split("=")
        if xx and xx[0] in HARMFUL:
            if m.from_user.id != OWNER_ID:
                out = "You can't access them"
                await c.send_message(
                    MESSAGE_DUMP,
                    f"@{m.from_user.username} TREID TO FETCH ENV OF BOT \n userid = {m.from_user.id}",
                )
            else:
                pass
        else:
            pass

    OUTPUT = ""
    OUTPUT += f"<b>QUERY:</b>\n<u>Command:</u>\n<code>{cmd}</code> \n"
    OUTPUT += f"<u>PID</u>: <code>{process.pid}</code>\n\n"
    OUTPUT += f"<b>stderr</b>: \n<code>{e}</code>\n\n"
    OUTPUT += f"<b>stdout</b>: \n<code>{out}</code>"

    try:
        await sm.edit_text(OUTPUT)
    except (MessageTooLong, EntityBoundsInvalid):
        with BytesIO(str.encode(await remove_markdown_and_html(OUTPUT))) as f:
            f.name = "sh.txt"
            await m.reply_document(
                document=f,
                caption=cmd,
                disable_notification=True,
                reply_to_message_id=reply_to_id,
            )
        await sm.delete()
    return


@Gojo.on_message(command("chatlist", dev_cmd=True))
async def chats(c: Gojo, m: Message):
    exmsg = await m.reply_text(text="Exporting Charlist...")
    await c.send_message(
        MESSAGE_DUMP,
        f"#CHATLIST\n\n**User:** {(await mention_markdown(m.from_user.first_name, m.from_user.id))}",
    )
    all_chats = (Chats.list_chats_full()) or {}
    chatfile = """List of chats in my database.

        <b>Chat name | Chat ID | Members count</b>"""
    P = 1
    for chat in all_chats:
        try:
            chat_info = await c.get_chat(chat["_id"])
            chat_members = chat_info.members_count
            try:
                invitelink = chat_info.invite_link
            except KeyError:
                invitelink = "No Link!"
            chatfile += f"{P}. {chat['chat_name']} | {chat['_id']} | {chat_members} | {invitelink}\n"
            P += 1
        except ChatAdminRequired:
            pass
        except (ChannelPrivate, ChannelInvalid):
            Chats.remove_chat(chat["_id"])
        except PeerIdInvalid:
            LOGGER.warning(f"Peer not found {chat['_id']}")
        except FloodWait as ef:
            LOGGER.error("FloodWait required, Sleeping for 60s")
            LOGGER.error(ef)
            sleep(60)
        except RPCError as ef:
            LOGGER.error(ef)
            await m.reply_text(f"**Error:**\n{ef}")

    with BytesIO(str.encode(await remove_markdown_and_html(chatfile))) as f:
        f.name = "chatlist.txt"
        await m.reply_document(
            document=f,
            caption="Here is the list of chats in my Database.",
        )
    await exmsg.delete()
    return


@Gojo.on_message(command("uptime", dev_cmd=True))
async def uptime(_, m: Message):
    up = strftime("%Hh %Mm %Ss", gmtime(time() - UPTIME))
    await m.reply_text(text=f"<b>Uptime:</b> <code>{up}</code>", quote=True)
    return


@Gojo.on_message(command("leavechat", dev_cmd=True))
async def leave_chat(c: Gojo, m: Message):
    if len(m.text.split()) != 2:
        await m.reply_text("Supply a chat id which I should leave!", quoet=True)
        return

    chat_id = m.text.split(None, 1)[1]

    replymsg = await m.reply_text(f"Trying to leave chat {chat_id}...", quote=True)
    try:
        await c.leave_chat(chat_id)
        await replymsg.edit_text(f"Left <code>{chat_id}</code>.")
    except PeerIdInvalid:
        await replymsg.edit_text("Haven't seen this group in this session!")
    except RPCError as ef:
        LOGGER.error(ef)
        await replymsg.edit_text(f"Failed to leave chat!\nError: <code>{ef}</code>.")
    return


@Gojo.on_message(command("chatbroadcast", dev_cmd=True))
async def chat_broadcast(c: Gojo, m: Message):
    if m.reply_to_message:
        msg = m.reply_to_message.text.markdown
    else:
        await m.reply_text("Reply to a message to broadcast it")
        return

    exmsg = await m.reply_text("Started broadcasting!")
    all_chats = (Chats.list_chats_by_id()) or {}
    err_str, done_broadcast = "", 0

    for chat in all_chats:
        try:
            await c.send_message(chat, msg, disable_web_page_preview=True)
            done_broadcast += 1
            await sleep(0.1)
        except RPCError as ef:
            LOGGER.error(ef)
            err_str += str(ef)
            continue

    await exmsg.edit_text(
        f"Done broadcasting ✅\nSent message to {done_broadcast} chats",
    )

    if err_str:
        with BytesIO(str.encode(await remove_markdown_and_html(err_str))) as f:
            f.name = "error_broadcast.txt"
            await m.reply_document(
                document=f,
                caption="Broadcast Error",
            )

    return


_DISABLE_CMDS_ = ["ping"]

__HELP__ = """
**DEV and SUDOERS commands**

**Dev's commands:**
• /logs : Return the logs of bot.
• /neofetch : Fetch neo.
• /eval : Evaluate the given python code.
• /exec : Execute the given code.
• /chatlist : Return the list of chats present in database
• /uptime : Return the uptime of the bot.
• /leavechat : Bot will leave the provided chat.
• /chatbroadcast : Broadcast the messge to chats.

**Sudoer's command:**
• /ping : return the ping of the bot.

**Example:**
/ping
"""
