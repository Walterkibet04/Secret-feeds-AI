"""
Secret Feeds — Tweet Rewriter (local CLI use)
Run: python rewrite.py
"""
from dotenv import load_dotenv
load_dotenv()

from generator import call_ai, REWRITE_PROMPT

DIVIDER = "─" * 60


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
            rewritten = call_ai(REWRITE_PROMPT.format(tweet=original))
            print(f"\n✅ Rewritten ({len(rewritten)}/4000 chars):")
            print(DIVIDER)
            print(rewritten)
            print(DIVIDER)
            print()
        except Exception as e:
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    main()
