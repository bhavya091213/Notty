import sys
import os
import time
import logging
import difflib
import hashlib
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from google import genai


API_KEY = os.getenv('GEMINI_KEY')
print(API_KEY)

def hash_lines(lines):
    """Return a hash for a list of lines to detect self-writes."""
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def clean_ai_output(text: str):
    """
    Clean AI output to remove extra code fences, boilerplate phrases, and duplicates.
    """
    lines = text.strip().splitlines()

    # Remove boilerplate phrases and code fences
    filtered = []
    for line in lines:
        if line.strip().lower().startswith("okay") and "markdown" in line.lower():
            continue
        if line.strip().startswith("```"):
            continue
        filtered.append(line)

    # Deduplicate consecutive lines
    seen = set()
    cleaned = []
    for line in filtered:
        if line not in seen:
            cleaned.append(line)
            seen.add(line)

    return cleaned


class DiffEnhancerHandler(FileSystemEventHandler):
    def __init__(self, target_file: Path, client: genai.Client, min_lines: int = 5, cooldown: int = 3):
        super().__init__()
        self.target_file = target_file.resolve()
        self.client = client
        self.file_snapshots = {}
        self.last_ai_hash = None
        self.min_lines = min_lines
        self.cooldown = cooldown
        self.last_processed_time = 0

        try:
            self.file_snapshots[self.target_file] = self.target_file.read_text(errors="ignore").splitlines()
        except Exception:
            self.file_snapshots[self.target_file] = []

    def on_modified(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path).resolve()
        if file_path != self.target_file:
            return

        # Cooldown to prevent rapid triggers
        now = time.time()
        if now - self.last_processed_time < self.cooldown:
            return

        try:
            new_content = file_path.read_text(errors="ignore").splitlines()
        except Exception as e:
            logging.error(f"Could not read {file_path}: {e}")
            return

        old_content = self.file_snapshots.get(file_path, [])
        diff = list(difflib.unified_diff(
            old_content, new_content,
            fromfile=f"{file_path} (old)",
            tofile=f"{file_path} (new)",
            lineterm=""
        ))

        if not diff:
            return
        
        # print(diff)
        # Only consider added lines (ignore deletions)
        changed_lines = []
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                if line[1:].strip():
                    changed_lines.append(line[1:])

        if not changed_lines:
            return

        # Ignore small changes
        if len(changed_lines) < self.min_lines:
            logging.info(f"Ignored change ({len(changed_lines)} lines < {self.min_lines})")
            self.file_snapshots[file_path] = new_content
            return

        # Ignore changes that match last AI output
        change_hash = hash_lines(changed_lines)
        if change_hash == self.last_ai_hash:
            logging.info("Ignored change caused by AI self-write")
            self.file_snapshots[file_path] = new_content
            return

        logging.info(f"Processing {len(changed_lines)} changed lines with AI...")

        # Build AI prompt
        prompt = """
        Take the text below and:  
        1. Correct spelling/errors only if wrong (spelling errors should be corrected in place)
        2. Do not remove or shorten content  (Only remove spelling errors)
        3. Add clarifying notes or supplemental info to improve understanding  (Supplemental information should be put in parenthesis and put under a bullet point or a sub bullet point, clarifications should be added same line by being bracketed)
        4. Preserve the original formatting, indentation, bullet points, and line breaks exactly as provided  
        5. Do not include code fences (```), apologies, or filler phrases in your response  
        6. Reply only once with the improved Markdown content  
        Notes:
        """
        finalPrompt = prompt + "\n".join(changed_lines)

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash", contents=finalPrompt
            )
            improved_text = clean_ai_output(response.text)
        except Exception as e:
            logging.error(f"AI request failed: {e}")
            return

        logging.info("AI response received, updating file...")

        # Patch file: replace entire block of changed lines once
        start_idx = None
        for idx, line in enumerate(new_content):
            if line.strip() == changed_lines[0].strip():
                start_idx = idx
                break

        if start_idx is not None:
            patched_content = new_content[:start_idx]
            patched_content.extend(improved_text)
            patched_content.extend(new_content[start_idx + len(changed_lines):])
        else:
            # fallback: append at end if no match
            patched_content = new_content + improved_text

        try:
            file_path.write_text("\n".join(patched_content), encoding="utf-8")
        except Exception as e:
            logging.error(f"Could not write changes to {file_path}: {e}")
            return

        # Save state
        self.file_snapshots[file_path] = patched_content
        self.last_ai_hash = hash_lines(improved_text)
        self.last_processed_time = time.time()
        logging.info(f"File updated with AI-enhanced content: {file_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")

    if len(sys.argv) < 2:
        print("Usage: python script.py /full/path/to/file.md")
        sys.exit(1)

    # Handle paths with spaces or quotes
    import shlex
    raw_path = " ".join(sys.argv[1:]).strip()
    raw_path = shlex.strip_quotes(raw_path) if hasattr(shlex, "strip_quotes") else raw_path.strip("\"'")
    target_file = Path(raw_path).expanduser().resolve()

    if not target_file.exists():
        print(f"Error: File does not exist: {target_file}")
        sys.exit(1)

    client = genai.Client(api_key=API_KEY)

    logging.info(f"Monitoring file: {target_file}")

    event_handler = DiffEnhancerHandler(target_file, client)
    observer = Observer()
    observer.schedule(event_handler, str(target_file.parent), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
