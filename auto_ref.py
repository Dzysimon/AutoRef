#    Copyright 2026 Zhiyu Duan
#    created on 2026-06-06-21h-44m
#    github: https://github.com/Dzysimon
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import argparse
import logging
import sys
import re
from abc import ABC, abstractmethod
from typing import List, Optional
import requests

# ==========================================
# Core Business Logic (Engine and Manager)
# ==========================================

class BaseBibtexEngine(ABC):
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

    @abstractmethod
    def fetch_bibtex(self, title: str) -> Optional[str]:
        pass

class DblpEngine(BaseBibtexEngine):
    def __init__(self, skip_preprint: bool = True):
        super().__init__()
        self.api_url = "https://dblp.org/search/publ/api"
        self.skip_preprint = skip_preprint

    def fetch_bibtex(self, title: str) -> Optional[str]:
        logging.info(f"Retrieving via DBLP engine: {title}")
        params = {"q": title, "format": "json", "h": 5}

        try:
            response = self.session.get(self.api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            hits = data.get("result", {}).get("hits", {}).get("hit", [])
            if not hits:
                logging.warning(f"DBLP matched no results for {title}")
                return None

            for index, hit in enumerate(hits):
                info = hit.get("info", {})
                venue = info.get("venue", "")
                key = info.get("key")

                if self.skip_preprint:
                    if "CoRR" in venue or "arXiv" in venue.lower():
                        logging.info(f"Automatically skipping preprint version (Venue: {venue})")
                        continue

                if key:
                    bib_url = f"https://dblp.org/rec/{key}.bib"
                    logging.info(f"Found target version (Venue: {venue}), downloading BibTeX...")
                    bib_response = self.session.get(bib_url, timeout=10)

                    if bib_response.status_code == 200:
                        return bib_response.text.strip()

            logging.warning(f"DBLP found entries but none matched filtering criteria for {title}")
            return None

        except requests.RequestException as e:
            logging.error(f"DBLP engine request failed: {str(e)}")
            return None

class BibtexManager:
    def __init__(self):
        self._engines: List[BaseBibtexEngine] = []

    def register_engine(self, engine: BaseBibtexEngine) -> None:
        if isinstance(engine, BaseBibtexEngine):
            self._engines.append(engine)
        else:
            raise TypeError("Engine must inherit from BaseBibtexEngine")

    @staticmethod
    def _clean_and_format_bibtex(bibtex_str: str) -> str:
        """Clean and format BibTeX: remove unnecessary fields, format authors, generate Google Scholar style keys"""
        # Extract BibTeX type and key
        first_line_match = re.match(r'^@(\w+)\{([^,]+),', bibtex_str)
        if not first_line_match:
            return bibtex_str
        
        bib_type = first_line_match.group(1)
        old_key = first_line_match.group(2)
        
        # Manually parse fields, handling nested braces
        fields = {}
        content = bibtex_str[bibtex_str.find('{') + 1:]
        content = content[:content.rfind('}')]  # Remove final }
        
        # Split fields (handle commas inside braces)
        current_field = ''
        brace_depth = 0
        i = 0
        while i < len(content):
            char = content[i]
            if char == '{':
                brace_depth += 1
            elif char == '}':
                brace_depth -= 1
            elif char == ',' and brace_depth == 0:
                # Field separator found
                if current_field.strip():
                    parts = current_field.split('=', 1)
                    if len(parts) == 2:
                        field_name = parts[0].strip().lower()
                        field_value = parts[1].strip()
                        # Remove outer braces
                        if field_value.startswith('{') and field_value.endswith('}'):
                            field_value = field_value[1:-1]
                        # Skip unwanted fields
                        if field_name not in {'timestamp', 'biburl', 'bibsource'}:
                            fields[field_name] = field_value
                current_field = ''
                i += 1
                continue
            current_field += char
            i += 1
        
        # Process last field
        if current_field.strip():
            parts = current_field.split('=', 1)
            if len(parts) == 2:
                field_name = parts[0].strip().lower()
                field_value = parts[1].strip()
                # Remove outer braces
                if field_value.startswith('{') and field_value.endswith('}'):
                    field_value = field_value[1:-1]
                if field_name not in {'timestamp', 'biburl', 'bibsource'}:
                    fields[field_name] = field_value
        
        # Extract information for generating new key
        author = fields.get('author', '')
        year = fields.get('year', '')
        title = fields.get('title', '')
        
        new_key = BibtexManager._generate_google_scholar_key(author, year, title, old_key)
        
        # Rebuild BibTeX
        result = f"@{bib_type}{{{new_key},\n"
        
        field_order = ['author', 'title', 'year', 'booktitle', 'journal', 'volume', 'number', 'pages', 'publisher', 'doi']
        
        # Check if publisher should be displayed
        publisher = fields.get('publisher', '')
        is_openreview = 'openreview' in publisher.lower() if publisher else False
        
        for field in field_order:
            if field in fields:
                # Skip publisher if it is OpenReview.net
                if field == 'publisher' and is_openreview:
                    continue
                
                value = fields[field]
                # Clean up extra whitespace and newlines
                if field in {'author', 'title', 'booktitle', 'journal', 'publisher'}:
                    value = re.sub(r'\s+', ' ', value)
                result += f"  {field} = {{{value}}},\n"
        
        # Add url only if no doi
        if 'doi' not in fields and 'url' in fields:
            value = fields['url']
            result += f"  url = {{{value}}},\n"
        
        # Add other fields not in the list (exclude editor, url, and already processed)
        exclude_fields = {'editor', 'url'} | set(field_order)
        for field, value in fields.items():
            if field not in exclude_fields:
                if field in {'author', 'title', 'booktitle', 'journal', 'publisher'}:
                    value = re.sub(r'\s+', ' ', value)
                result += f"  {field} = {{{value}}},\n"
        
        result = result.rstrip(',\n') + '\n}'
        return result

    @staticmethod
    def _generate_google_scholar_key(author: str, year: str, title: str, fallback_key: str) -> str:
        """Generate Google Scholar style key: author + year + first title word"""
        if not author or not year or not title:
            return fallback_key
        
        # Extract first author's last name
        author_clean = re.sub(r'\{|\}', '', author)
        authors = author_clean.split(' and ')
        if authors:
            first_author = authors[0].strip()
            # If comma present, take part before comma (Western name order: First Last)
            if ',' in first_author:
                author_last = first_author.split(',')[0].strip()
            else:
                # Take last word as surname
                parts = first_author.split()
                author_last = parts[-1].strip() if parts else ''
            
            author_key = author_last.lower()
        else:
            author_key = ''
        
        # Extract year
        year_match = re.search(r'\d{4}', year)
        year_key = year_match.group(0) if year_match else ''
        
        # Extract first meaningful word from title (3+ characters)
        title_clean = re.sub(r'\{|\}', '', title)
        words = title_clean.split()
        title_key = ''
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r'[^a-zA-Z0-9]', '', word).lower()
            if len(clean_word) >= 3 and clean_word not in {'the', 'and', 'for', 'with', 'from'}:
                title_key = clean_word
                break
        
        if not title_key and words:
            # If not found, take first word
            title_key = re.sub(r'[^a-zA-Z0-9]', '', words[0]).lower()
        
        # Combine key
        if author_key and year_key and title_key:
            return f"{author_key}{year_key}{title_key}"
        else:
            return fallback_key

    def get_bibtex(self, title: str) -> Optional[str]:
        if not self._engines:
            logging.error("No retrieval engines registered in manager")
            return None

        for engine in self._engines:
            try:
                result = engine.fetch_bibtex(title)
                if result:
                    logging.info("Successfully retrieved BibTeX data")
                    # Clean and format BibTeX
                    result = self._clean_and_format_bibtex(result)
                    return result
            except Exception as e:
                logging.error(f"Engine internal error: {e}")
                continue

        logging.error(f"No engine could retrieve matching BibTeX for {title}")
        return None

# ==========================================
# CLI Command Line Interface
# ==========================================

def setup_logging(verbose: bool):
    """Configure logging display level"""
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level, 
        format="%(asctime)s - [%(levelname)s] - %(message)s",
        datefmt="%H:%M:%S"
    )

def main():
    # 1. Define command-line arguments
    parser = argparse.ArgumentParser(
        description="Academic paper BibTeX retrieval CLI tool (based on DBLP and other open APIs)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        "title", 
        type=str, 
        nargs='?',
        help="Full title of the paper to retrieve (wrap in quotes). Or use -f to specify a text file with multiple titles."
    )
    
    parser.add_argument(
        "-f", "--file",
        type=str,
        metavar="FILE",
        help="Text file containing paper titles, one per line. Will retrieve and generate ref.bib file."
    )
    
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        metavar="FILE",
        help="Save retrieved BibTeX to specified file (example: refs.bib). If not specified, print to terminal."
    )
    
    parser.add_argument(
        "--allow-preprint", 
        action="store_true", 
        help="Allow retrieving preprint versions from arXiv/CoRR (default: filter preprints, require formal conference/journal versions)"
    )
    
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Show detailed execution process and logging information"
    )

    args = parser.parse_args()

    # 2. Validate arguments
    if not args.title and not args.file:
        parser.print_help()
        sys.exit(1)

    # 3. Initialize environment
    setup_logging(args.verbose)
    
    manager = BibtexManager()
    dblp_engine = DblpEngine(skip_preprint=not args.allow_preprint)
    manager.register_engine(dblp_engine)

    # 4. Process single title or file mode
    if args.file:
        # Batch processing mode
        process_titles_from_file(manager, args.file, args.output, args.verbose)
    else:
        # Single title mode
        process_single_title(manager, args.title, args.output)

def process_single_title(manager: BibtexManager, title: str, output_file: Optional[str]) -> None:
    """Process a single paper title"""
    bibtex_data = manager.get_bibtex(title)

    if bibtex_data:
        if output_file:
            try:
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(bibtex_data + "\n\n")
                print(f"Success. BibTeX appended to: {output_file}")
            except IOError as e:
                print(f"File write failed: {e}", file=sys.stderr)
        else:
            print("\n" + "-"*40)
            print(bibtex_data)
            print("-"*40 + "\n")
    else:
        sys.exit(1)

def process_titles_from_file(manager: BibtexManager, file_path: str, output_file: Optional[str], verbose: bool) -> None:
    """Read titles from file line by line and retrieve BibTeX in batch"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            titles = [line.strip() for line in f if line.strip()]
    except IOError as e:
        print(f"File read failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not titles:
        print("No titles found in file", file=sys.stderr)
        sys.exit(1)

    # Determine output file (default to ref.bib if not specified)
    if not output_file:
        output_file = "ref.bib"
    
    # Clear output file
    try:
        open(output_file, 'w', encoding='utf-8').close()
    except IOError as e:
        print(f"Cannot create output file {output_file}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(titles)} titles, starting batch retrieval...")
    success_count = 0
    failed_titles = []

    for idx, title in enumerate(titles, 1):
        print(f"\n[{idx}/{len(titles)}] Retrieving: {title[:60]}{'...' if len(title) > 60 else ''}")
        bibtex_data = manager.get_bibtex(title)
        
        if bibtex_data:
            try:
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write(bibtex_data + "\n\n")
                print(f"  Successfully retrieved")
                success_count += 1
            except IOError as e:
                print(f"  File write failed: {e}", file=sys.stderr)
                failed_titles.append((title, f"Write error: {e}"))
        else:
            print(f"  BibTeX not found")
            failed_titles.append((title, "Not found"))

    # Output statistics
    print(f"\n{'='*50}")
    print(f"Retrieval completed")
    print(f"Success: {success_count}/{len(titles)}")
    print(f"Failed: {len(failed_titles)}/{len(titles)}")
    
    if failed_titles:
        print(f"\nFailed titles:")
        for title, reason in failed_titles:
            print(f"  - {title[:60]}{'...' if len(title) > 60 else ''} ({reason})")
    
    if success_count > 0:
        print(f"\nAll BibTeX entries saved to: {output_file}")

if __name__ == "__main__":
    main()