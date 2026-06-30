import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key="AQ.Ab8RN6Izz5rWeJMWjB4ShB9TxUn-ePbkSP-BX7431iaoaKss4A")
MODEL = "gemini-2.0-flash"

DIVIDER = "─" * 60

PROMPT = """You are helping rewrite a tweet for Secret Feeds, a news account on X.

GOAL: Make the tweet look original to X's algorithm without changing what it says.

STRICT RULES:
1. Keep EVERY fact, number, name, and date exactly the same
2. Do NOT add new information
3. Do NOT remove any information
4. Do NOT change the meaning even slightly
5. Use simple everyday English
6. Just rearrange the sentence structure and swap some words with synonyms
7. Keep it under 280 characters
8. Do not add hashtags or emojis unless the original has them

If the original says "235 people died", your version must still say "235 people died" — not "hundreds died". Exact numbers and names must stay.

Original tweet:
"{tweet}"

Write ONLY the rewritten tweet. Nothing else."""


def rewrite(original):
    response = client.models.generate_content(model=MODEL, contents=PROMPT.format(tweet=original))
    return response.text.strip()


def main():
    print(f"\n{'='*60}")
    print("  SECRET FEEDS — Tweet Rewriter")
    print("  Same message. Different words. Beats X duplicate filter.")
    print(f"{'='*60}\n")

    while True:
        print("Paste the tweet (or type 'quit'):")
        print(DIVIDER)
        original = input("> ").strip()
        print(DIVIDER)

        if original.lower() in ("quit", "exit", "q"):
            break
        if not original:
            print("Nothing entered. Try again.\n")
            continue

        print("\n⏳ Rewriting...")
        try:
            rewritten = rewrite(original)
            print(f"\n✅ Rewritten ({len(rewritten)}/280 chars):")
            print(DIVIDER)
            print(rewritten)
            print(DIVIDER)
            print()
        except Exception as e:
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    main()
