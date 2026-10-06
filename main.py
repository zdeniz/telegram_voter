import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.messages import SendVoteRequest
from telethon.errors import FloodWaitError

# These example values won't work. You must get your own api_id and
# api_hash from https://my.telegram.org, under API Development.
ACCOUNTS_CONFIG = [
    {
        "session": "user_session_1", 
        "api_id": 1234567, 
        "api_hash": "hash_1"
    },
]

# Maps question keywords/patterns to target answer keywords or fallback indices
POLL_RULES = [
    {
        "question_keyword": " Bir sonraki iş günü için:",
        # Vote for these if available
        "target_answers": [
            "Öğle yemeği istiyorum"
            # , "Servis kullanacağım"
        ],
        # Fallback to 1st option if keywords not found
        "fallback_indices": [0],
    },
]

# Can be a chat name from user history or a chat id int
TARGET_CHANNEL = "Aspendos Tüm Bina"


def get_plain_text(obj) -> str:
    """Safely extracts plain text string handling Telethon's TextWithEntities or standard str."""
    if hasattr(obj, "text"):
        return str(obj.text)
    return str(obj)


def select_vote_options(poll, answers):
    """Matches poll question against rules dictionary and resolves target option bytes."""
    question = get_plain_text(poll.question).lower()
    matched_rule = None

    for rule in POLL_RULES:
        if rule.get("default"):
            matched_rule = rule
            continue
        if rule.get("question_keyword", "").lower() in question:
            matched_rule = rule
            break

    target_bytes = []

    # Match by target answer text keywords
    if matched_rule.get("target_answers"):
        for answer in answers:
            ans_text = get_plain_text(answer.text).lower()
            if any(kw.lower() in ans_text for kw in matched_rule["target_answers"]):
                target_bytes.append(answer.option)
                if not poll.multiple_choice:
                    break

    # Fallback to specific indices if no keyword matched, disabled for now
    # if not target_bytes and matched_rule.get("fallback_indices"):
    #     for idx in matched_rule["fallback_indices"]:
    #         if idx < len(answers):
    #             target_bytes.append(answers[idx].option)

    return target_bytes


async def cast_vote(client, peer, message_id, poll, answers, account_label):
    """Calculates choices and sends SendVoteRequest with error handling."""
    options = select_vote_options(poll, answers)
    if not options:
        print(f"[{account_label}] No valid options resolved for poll.")
        return

    try:
        await client(SendVoteRequest(peer=peer, msg_id=message_id, options=options))
        print(f"[{account_label}] Successfully voted with options: {options}")
    except FloodWaitError as e:
        print(f"[{account_label}] Rate limited. Must wait {e.seconds} seconds.")
    except Exception as e:
        print(f"[{account_label}] Failed to vote: {e}")


async def resolve_chat_entity(client, chat_target):
    """Resolves chat target whether provided as int ID or string display name."""
    if isinstance(chat_target, int):
        return await client.get_entity(chat_target)

    # Match string display name against active dialogs
    async for dialog in client.iter_dialogs():
        if dialog.name == chat_target or dialog.title == chat_target:
            return dialog.entity

    # Fallback resolver for @usernames or invite links
    return await client.get_entity(chat_target)


async def run_account_worker(acc_info):
    label = acc_info["session"]
    client = TelegramClient(
        acc_info["session"], acc_info["api_id"], acc_info["api_hash"]
    )

    await client.start()
    print(f"[{label}] Account connected.")

    try:
        # Step 0: Resolve Target Chat
        chat = await resolve_chat_entity(client, TARGET_CHANNEL)
        chat_title = getattr(chat, "title", str(chat.id))
        print(f"[{label}] Resolved chat: '{chat_title}' (ID: {chat.id})")

        # Step 1 & 2: Check history for latest unclosed poll and vote
        print(f"[{label}] Checking recent history for active polls...")
        async for message in client.iter_messages(chat, limit=50):
            if message.media and hasattr(message.media, "poll"):
                poll = message.media.poll
                poll_text = get_plain_text(poll.question)

                if poll.closed:
                    print(f"[{label}] Skipping closed poll in history: '{poll_text}'")
                    continue

                print(
                    f"[{label}] Found active historical poll: '{poll_text}' (Msg ID: {message.id})"
                )
                await cast_vote(
                    client=client,
                    peer=chat,
                    message_id=message.id,
                    poll=poll,
                    answers=poll.answers,
                    account_label=label,
                )
                break  # Process only the latest open poll from history

        # Step 3: Attach event listener to listen for new polls forever
        @client.on(events.NewMessage(chats=chat))
        async def on_new_message(event):
            if event.message.media and hasattr(event.message.media, "poll"):
                poll = event.message.media.poll
                poll_text = get_plain_text(poll.question)

                if poll.closed:
                    return

                print(
                    f"\n[{label}] New Live Poll Detected: '{poll_text}' (Msg ID: {event.message.id})"
                )
                await cast_vote(
                    client=client,
                    peer=event.chat_id,
                    message_id=event.message.id,
                    poll=poll,
                    answers=poll.answers,
                    account_label=label,
                )

        print(
            f"[{label}] Now listening to '{chat_title}' continuously for future polls...\n"
        )
        await client.run_until_disconnected()

    except Exception as e:
        print(f"[{label}] Worker execution error: {e}")
    finally:
        if client.is_connected():
            await client.disconnect()


async def main():
    tasks = [run_account_worker(acc) for acc in ACCOUNTS_CONFIG]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
