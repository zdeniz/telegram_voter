import asyncio
import sys
from datetime import datetime

import yaml
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import SendVoteRequest


def log(message: str) -> None:
    """print() with a timestamp at the start of the line."""
    if message.startswith("\n"):  # keep the blank separator line, put the timestamp on the text
        print()
        message = message.lstrip("\n")
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}", flush=True)


def load_config(file_path="config.yaml"):
    """Loads YAML configuration using PyYAML."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        sys.exit(f"Error: Configuration file '{file_path}' not found.")


CONFIG = load_config()
TARGET_CHANNEL = CONFIG.get("target_channel")
ACCOUNTS_CONFIG = CONFIG.get("accounts", [])
HISTORY_LIMIT = 50  # how many recent messages to scan for the latest poll on startup


def clean(text) -> str:
    """For LOG OUTPUT ONLY: collapses every whitespace run (spaces, \r, \n, \t) into one space."""
    return " ".join(str(text).split())


def get_plain_text(obj) -> str:
    """Handles Telethon's TextWithEntities as well as plain str. Strips leading/trailing whitespace."""
    if hasattr(obj, "text"):
        return str(obj.text).strip()
    return str(obj).strip()


def select_vote_options(poll, rules):
    """
    Keyword rules are tried first (in config order), then the default_fallback rule.
    """
    question = get_plain_text(poll.question)

    candidates = []
    default_rule = None
    for rule in rules:
        keyword = str(rule.get("question_keyword") or "").strip()
        if keyword:
            if keyword in question:
                candidates.append(rule)
        elif rule.get("default_fallback") and default_rule is None:
            default_rule = rule
    if default_rule:
        candidates.append(default_rule)

    for rule in candidates:
        chosen = []

        targets = [str(t).strip() for t in (rule.get("target_answers") or [])]
        if targets:
            for answer in poll.answers:
                if get_plain_text(answer.text) in targets:
                    chosen.append(answer.option)
                    if not poll.multiple_choice:
                        break

        if not chosen:
            for idx in rule.get("fallback_indices") or []:
                if 0 <= idx < len(poll.answers):
                    chosen.append(poll.answers[idx].option)
                    if not poll.multiple_choice:
                        break

        if chosen:
            return chosen

    return []


def current_choices(message) -> list:
    """Option bytes this account has currently voted for (empty list = not voted)."""
    results = getattr(message.media, "results", None)
    rows = getattr(results, "results", None) or []
    return [r.option for r in rows if getattr(r, "chosen", False)]


async def cast_vote(client, chat, message, label, rules, voted_ids):
    poll = message.media.poll
    poll_text = clean(get_plain_text(poll.question))  # used in log lines only

    # Closed poll: nothing can be done.
    if poll.closed:
        log(f"[{label}] Poll is closed, skipping: '{poll_text}'")
        return

    # Already handled in this session (e.g. startup scan vs. live handler).
    if message.id in voted_ids:
        return

    options = select_vote_options(poll, rules)
    if not options:
        shown = [clean(get_plain_text(a.text)) for a in poll.answers]
        log(f"[{label}] No rule matched poll '{poll_text}'. Answers were: {shown}")
        return

    previous = current_choices(message)
    if previous:
        # Already voted: change the vote only if it differs from what the rules want.
        if set(previous) == set(options):
            log(f"[{label}] Already voted as per rules on poll {message.id}, nothing to change.")
            voted_ids.add(message.id)
            return
        if poll.quiz or getattr(poll, "revoting_disabled", False):
            log(f"[{label}] Poll {message.id} does not allow changing votes, skipping.")
            voted_ids.add(message.id)
            return
        log(f"[{label}] Changing vote on poll {message.id}: {previous} -> {options}")
        action = "Changed vote"
    else:
        action = "Voted"

    voted_ids.add(
        message.id
    )  # claim it first so the startup check and the live handler can't double-vote
    for attempt in range(2):
        try:
            await client(SendVoteRequest(peer=chat, msg_id=message.id, options=options))
            log(f"[{label}] {action} on '{poll_text}' with options: {options}")
            return
        except FloodWaitError as e:
            log(f"[{label}] Rate limited, waiting {e.seconds}s...")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            log(f"[{label}] Failed to vote: {e}")
            voted_ids.discard(message.id)
            return
    voted_ids.discard(message.id)


async def resolve_chat_entity(client, chat_target):
    """Resolves an int ID, a dialog display name, a @username or an invite link."""
    if isinstance(chat_target, int):
        return await client.get_entity(chat_target)

    async for dialog in client.iter_dialogs():
        if dialog.name == chat_target:
            return dialog.entity

    return await client.get_entity(chat_target)


async def run_account_worker(client, acc_info):
    label = acc_info["session"]
    rules = acc_info.get("rules", [])
    voted_ids = set()

    try:
        chat = await resolve_chat_entity(client, TARGET_CHANNEL)
        chat_title = clean(getattr(chat, "title", None) or chat.id)
        log(f"[{label}] Resolved chat: '{chat_title}' (ID: {chat.id})")

        # Register the live handler first so nothing is missed during the startup check.
        @client.on(events.NewMessage(chats=chat))
        async def on_new_message(event):
            media = event.message.media
            if media and hasattr(media, "poll"):
                log(
                    f"\n[{label}] New poll: '{clean(get_plain_text(media.poll.question))}' "
                    f"(Msg ID: {event.message.id})"
                )
                await cast_vote(client, chat, event.message, label, rules, voted_ids)

        # Look back through recent history for the most recent poll (newest first).
        log(
            f"[{label}] Searching the last {HISTORY_LIMIT} messages for the latest poll..."
        )
        found_poll = False
        async for message in client.iter_messages(chat, limit=HISTORY_LIMIT):
            if message.media and hasattr(message.media, "poll"):
                found_poll = True
                log(
                    f"[{label}] Latest poll is Msg ID {message.id}: "
                    f"'{clean(get_plain_text(message.media.poll.question))}'"
                )
                await cast_vote(client, chat, message, label, rules, voted_ids)
                break  # only the most recent poll; if it's closed, cast_vote just reports it
        if not found_poll:
            log(f"[{label}] No poll found in the last {HISTORY_LIMIT} messages.")

        log(f"[{label}] Listening to '{chat_title}' for upcoming polls...\n")
        await client.run_until_disconnected()

    except Exception as e:
        log(f"[{label}] Worker execution error: {e}")
    finally:
        if client.is_connected():
            await client.disconnect()


async def main():
    if not ACCOUNTS_CONFIG:
        log("No accounts defined in configuration file.")
        return

    # Log in sequentially: client.start() may prompt for phone/code on stdin,
    # and concurrent prompts from several accounts would collide.
    logged_in = []
    for acc in ACCOUNTS_CONFIG:
        client = TelegramClient(acc["session"], acc["api_id"], acc["api_hash"])
        await client.start()  # type: ignore[misc]  # Telethon's typing is wrong here; it is awaitable in async code
        log(f"[{acc['session']}] Account connected.")
        logged_in.append((client, acc))

    await asyncio.gather(*(run_account_worker(c, a) for c, a in logged_in))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
