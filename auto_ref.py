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
import time
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
        self.timeout = 20  # Increased from 10s to accommodate network latency
        self.max_retries = 2  # Retry up to 2 times on transient failures
        self.retry_delay = 1.5  # Wait 1.5s between retries with exponential backoff

    def fetch_bibtex(self, title: str) -> Optional[str]:
        logging.info(f"[DBLP] Querying for: {title}")
        params = {"q": title, "format": "json", "h": 5}

        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(self.api_url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                hits = data.get("result", {}).get("hits", {}).get("hit", [])
                if not hits:
                    logging.debug(f"[DBLP] No results found for: {title}")
                    return None

                for index, hit in enumerate(hits):
                    info = hit.get("info", {})
                    venue = info.get("venue", "")
                    key = info.get("key")

                    if self.skip_preprint:
                        if "CoRR" in venue or "arXiv" in venue.lower():
                            logging.debug(f"[DBLP] Skipping preprint entry (Venue: {venue})")
                            continue

                    if key:
                        bib_url = f"https://dblp.org/rec/{key}.bib"
                        logging.debug(f"[DBLP] Found entry (Venue: {venue}), downloading BibTeX...")
                        
                        # Retry logic for BibTeX download
                        bib_response = None
                        for bib_attempt in range(2):
                            try:
                                bib_response = self.session.get(bib_url, timeout=self.timeout)
                                if bib_response.status_code == 200:
                                    logging.info(f"[DBLP] Successfully retrieved BibTeX from: {venue}")
                                    return bib_response.text.strip()
                            except requests.RequestException:
                                if bib_attempt == 0:
                                    time.sleep(self.retry_delay)
                                    continue
                                else:
                                    break

                logging.debug(f"[DBLP] Found entries but none matched preprint filter criteria")
                return None

            except requests.Timeout:
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (attempt + 1)
                    logging.warning(f"[DBLP] Timeout (attempt {attempt + 1}/{self.max_retries + 1}), retrying in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logging.error(f"[DBLP] Failed after {self.max_retries + 1} attempts: Request timeout")
                    return None
            except requests.ConnectionError:
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (attempt + 1)
                    logging.warning(f"[DBLP] Connection error (attempt {attempt + 1}/{self.max_retries + 1}), retrying in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logging.error(f"[DBLP] Failed after {self.max_retries + 1} attempts: Connection error")
                    return None
            except requests.RequestException as e:
                logging.error(f"[DBLP] Request failed: {type(e).__name__}")
                return None

        return None
    
class SemanticScholarEngine(BaseBibtexEngine):
    """Semantic Scholar retrieval engine.
    
    Covers extensive multidisciplinary literature with excellent support for AI and related fields.
    Official API natively supports BibTeX format return.
    """
    def __init__(self, skip_preprint: bool = True):
        super().__init__()
        self.api_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        self.skip_preprint = skip_preprint
        self.timeout = 20

    def fetch_bibtex(self, title: str) -> Optional[str]:
        logging.info(f"[SemanticScholar] Querying for: {title}")
        # Request fields: venue (journal/conference), publicationTypes (paper type), citationStyles (BibTeX format)
        params = {
            "query": title,
            "limit": 3,
            "fields": "title,venue,publicationTypes,citationStyles"
        }
        
        try:
            response = self.session.get(self.api_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            hits = data.get("data", [])
            if not hits:
                logging.debug(f"[SemanticScholar] No results found for: {title}")
                return None
                
            for hit in hits:
                venue = hit.get("venue", "")
                pub_types = hit.get("publicationTypes") or []
                
                if self.skip_preprint:
                    # Filter out arXiv and Review (preprint review stage) entries
                    if "arxiv" in venue.lower() or "corr" in venue.lower() or "Review" in pub_types:
                        logging.debug(f"[SemanticScholar] Skipping preprint entry (Venue: {venue})")
                        continue
                
                bibtex = hit.get("citationStyles", {}).get("bibtex")
                if bibtex:
                    logging.info(f"[SemanticScholar] Successfully retrieved BibTeX (Venue: {venue})")
                    return bibtex.strip()
                    
            return None
        except requests.Timeout:
            logging.warning(f"[SemanticScholar] Request timeout for: {title}")
            return None
        except requests.RequestException as e:
            logging.debug(f"[SemanticScholar] Request error: {type(e).__name__}")
            return None
        except Exception as e:
            logging.error(f"[SemanticScholar] Unexpected error: {e}")
            return None
        
class CrossRefEngine(BaseBibtexEngine):
    """CrossRef retrieval engine.
    
    Most powerful multidisciplinary fallback engine. If a paper has an assigned DOI, it can be found here.
    Uses doi.org content negotiation to retrieve authentic BibTeX format directly.
    """
    def __init__(self, skip_preprint: bool = True):
        super().__init__()
        self.search_url = "https://api.crossref.org/works"
        self.skip_preprint = skip_preprint
        self.timeout = 20
        # CrossRef strongly recommends including email in User-Agent to get allocated to faster "Polite Pool"
        self.session.headers.update({
            "User-Agent": "AutoRef_Bot/1.0 (mailto:developer@example.com)"
        })

    def fetch_bibtex(self, title: str) -> Optional[str]:
        logging.info(f"[CrossRef] Querying for: {title}")
        params = {
            "query.bibliographic": title,
            "select": "DOI,title,type,container-title",
            "rows": 3
        }
        
        try:
            response = self.session.get(self.search_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            items = data.get("message", {}).get("items", [])
            if not items:
                logging.debug(f"[CrossRef] No results found for: {title}")
                return None
                
            for item in items:
                pub_type = item.get("type", "")
                venue = item.get("container-title", [""])[0] if item.get("container-title") else ""
                doi = item.get("DOI")
                
                if self.skip_preprint:
                    # CrossRef strictly marks preprints with 'posted-content' type
                    if pub_type == "posted-content":
                        logging.debug(f"[CrossRef] Skipping preprint entry (Type: {pub_type})")
                        continue
                        
                if doi:
                    logging.debug(f"[CrossRef] Found DOI: {doi}, negotiating BibTeX format...")
                    # Use HTTP Accept header to request BibTeX format from doi.org
                    bib_response = self.session.get(
                        f"https://doi.org/{doi}", 
                        headers={"Accept": "application/x-bibtex"},
                        timeout=self.timeout
                    )
                    if bib_response.status_code == 200:
                        logging.info(f"[CrossRef] Successfully retrieved BibTeX from DOI: {doi}")
                        return bib_response.text.strip()
                        
            return None
        except requests.Timeout:
            logging.warning(f"[CrossRef] Request timeout for: {title}")
            return None
        except requests.RequestException as e:
            logging.debug(f"[CrossRef] Request error: {type(e).__name__}")
            return None
        except Exception as e:
            logging.error(f"[CrossRef] Unexpected error: {e}")
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
            logging.error("[Manager] No retrieval engines registered")
            return None

        engines_attempted = []
        for i, engine in enumerate(self._engines, 1):
            try:
                engine_name = engine.__class__.__name__
                result = engine.fetch_bibtex(title)
                if result:
                    logging.info(f"[Manager] Retrieved BibTeX via {engine_name} ({i}/{len(self._engines)})")
                    # Clean and format BibTeX
                    result = self._clean_and_format_bibtex(result)
                    return result
                engines_attempted.append(engine_name)
            except Exception as e:
                logging.error(f"[Manager] {engine.__class__.__name__} error: {e}")
                continue

        logging.warning(f"[Manager] All {len(self._engines)} engines failed for: {title}")
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
    # Define command-line arguments
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

    # Validate arguments
    if not args.title and not args.file:
        parser.print_help()
        sys.exit(1)

    # Initialize environment
    setup_logging(args.verbose)
    
    manager = BibtexManager()
    
    # Determine preprint filtering based on command-line arguments
    skip_prep = not args.allow_preprint
    
    # Register engines (order defines priority for fallback)
    manager.register_engine(DblpEngine(skip_preprint=skip_prep))
    manager.register_engine(SemanticScholarEngine(skip_preprint=skip_prep))
    manager.register_engine(CrossRefEngine(skip_preprint=skip_prep))

    # Process single title or file mode
    if args.file:
        # Batch processing mode
        process_titles_from_file(manager, args.file, args.output, args.verbose)
    else:
        # Single title mode
        process_single_title(manager, args.title, args.output)

def process_single_title(manager: BibtexManager, title: str, output_file: Optional[str]) -> None:
    """Process a single paper title and output result"""
    logging.info(f"[CLI] Processing single title: {title}")
    bibtex_data = manager.get_bibtex(title)

    if bibtex_data:
        if output_file:
            try:
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(bibtex_data + "\n\n")
                print(f"[SUCCESS] BibTeX appended to: {output_file}")
                logging.info(f"[CLI] Successfully saved to file: {output_file}")
            except IOError as e:
                print(f"[ERROR] File write failed: {e}", file=sys.stderr)
                logging.error(f"[CLI] Failed to write file {output_file}: {e}")
        else:
            print("\n" + "="*50)
            print(bibtex_data)
            print("="*50 + "\n")
            logging.info(f"[CLI] Successfully printed BibTeX to stdout")
    else:
        print("[ERROR] Failed to retrieve BibTeX for the given title", file=sys.stderr)
        sys.exit(1)

def process_titles_from_file(manager: BibtexManager, file_path: str, output_file: Optional[str], verbose: bool) -> None:
    """Read titles from file line by line and retrieve BibTeX in batch mode"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            titles = [line.strip() for line in f if line.strip()]
    except IOError as e:
        print(f"[ERROR] File read failed: {e}", file=sys.stderr)
        logging.error(f"[CLI] Failed to read file {file_path}: {e}")
        sys.exit(1)

    if not titles:
        print("[ERROR] No titles found in file", file=sys.stderr)
        logging.error(f"[CLI] File {file_path} contains no valid titles")
        sys.exit(1)

    # Determine output file (default to ref.bib if not specified)
    if not output_file:
        output_file = "ref.bib"
    
    # Clear output file
    try:
        open(output_file, 'w', encoding='utf-8').close()
    except IOError as e:
        print(f"[ERROR] Cannot create output file {output_file}: {e}", file=sys.stderr)
        logging.error(f"[CLI] Failed to create output file {output_file}: {e}")
        sys.exit(1)

    print(f"[INFO] Found {len(titles)} titles, starting batch retrieval...")
    logging.info(f"[CLI] Starting batch processing of {len(titles)} titles")
    success_count = 0
    failed_titles = []

    for idx, title in enumerate(titles, 1):
        print(f"\n[{idx}/{len(titles)}] Retrieving: {title[:70]}{'...' if len(title) > 70 else ''}")
        bibtex_data = manager.get_bibtex(title)
        
        if bibtex_data:
            try:
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write(bibtex_data + "\n\n")
                print(f"  [OK] Successfully retrieved")
                success_count += 1
            except IOError as e:
                print(f"  [ERROR] File write failed: {e}", file=sys.stderr)
                logging.error(f"[CLI] Failed to write BibTeX for title {idx}: {e}")
                failed_titles.append((title, f"Write error: {e}"))
        else:
            print(f"  [SKIP] No BibTeX found")
            failed_titles.append((title, "Not found"))
        
        # Add delay between requests to respect API rate limits (except after last request)
        if idx < len(titles):
            time.sleep(0.5)

    # Output statistics
    print(f"\n{'='*50}")
    print(f"[SUMMARY] Batch retrieval completed")
    print(f"[SUMMARY] Success: {success_count}/{len(titles)}")
    print(f"[SUMMARY] Failed: {len(failed_titles)}/{len(titles)}")
    
    if failed_titles:
        print(f"\n[INFO] Failed titles:")
        for title, reason in failed_titles:
            print(f"  - {title[:70]}{'...' if len(title) > 70 else ''} ({reason})")
    
    if success_count > 0:
        print(f"\n[SUCCESS] All BibTeX entries saved to: {output_file}")
        logging.info(f"[CLI] Batch processing completed: {success_count}/{len(titles)} successful")
    else:
        print(f"\n[WARNING] No BibTeX entries could be retrieved")
        logging.warning(f"[CLI] Batch processing failed: 0/{len(titles)} successful")

if __name__ == "__main__":
    main()