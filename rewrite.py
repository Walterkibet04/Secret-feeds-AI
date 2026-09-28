from dotenv import load_dotenv
load_dotenv()
from generator import call_ai, FORMATS, pick_format, build_rewrite_prompt
from checks import check_post, clean_text

DIVIDER = "─" * 60

def main():
    import world_facts
    world_facts.load_cache()
    if not world_facts._cache['countries']:
        world_facts.refresh()
    print(f"\n{'='*60}")
    print("  SECRET FEEDS — Tweet Rewriter (CLI)")
    print(f"{'='*60}\n")
    while True:
        print("Paste the tweet (or type 'quit'):")
        print(DIVIDER)
        original = input("> ").strip()
        print(DIVIDER)
        if original.lower() in ("quit", "exit", "q"):
            break
        if not original:
            print("Nothing entered.\n")
            continue
        print("\n⏳ Rewriting...")
        try:
            fmt = pick_format("auto")
            rewritten = clean_text(call_ai(build_rewrite_prompt(original, fmt)))
            print(f"\n✅ Rewritten · {FORMATS[fmt]['label']} ({len(rewritten)}/4000 chars):")
            print(DIVIDER)
            print(rewritten)
            print(DIVIDER)
            for w in check_post(rewritten):
                print(f"⚠️  {w}")
            print()
        except Exception as e:
            print(f"❌ Error: {e}\n")

if __name__ == "__main__":
    main()
