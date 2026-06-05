# AutoRef - Academic Paper BibTeX Retrieval Tool

A powerful command-line utility for automatically retrieving BibTeX entries for academic papers using DBLP and other open APIs. Streamline your bibliography management workflow with one command.

## Features

### Core Capabilities
- **Automatic BibTeX Retrieval**: Search academic papers by title and instantly get properly formatted BibTeX entries
- **Multi-Source Support**: Extensible architecture supporting multiple retrieval engines (currently DBLP, easily expandable)
- **Batch Processing**: Process entire reading lists by providing a text file with paper titles
- **Smart Filtering**: Automatically filter and prioritize peer-reviewed conference/journal versions over preprints
- **Intelligent Key Generation**: Auto-generate Google Scholar-style citation keys (LastnameYearFirstword)

### Advanced Features
- **Automatic Field Cleaning**: Remove redundant metadata (timestamps, URLs for OpenReview entries)
- **Flexible Output Options**: Print to terminal or save directly to BibTeX files
- **Graceful Error Handling**: Continue processing on failures with detailed error reporting
- **Verbose Logging**: Optional detailed execution logs for debugging and optimization
- **Author-aware Processing**: Proper handling of multi-author papers and various naming conventions

## Installation

### Prerequisites
- Python 3.6+
- `requests` library

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd autoRef

# Install dependencies
pip install requests

# Make executable (optional)
chmod +x auto_ref.py
```

## Usage

### Basic Usage - Single Paper

Retrieve BibTeX for a single paper by title:
```bash
python auto_ref.py "Attention Is All You Need"
```

Output to terminal (formatted BibTeX display):
```
----------------------------------------
@inproceedings{vaswani2017attention,
  author = {Ashish Vaswani and Noam Shazeer and ...},
  title = {Attention Is All You Need},
  year = {2017},
  booktitle = {Advances in Neural Information Processing Systems}
}
----------------------------------------
```

### Save to File

Append BibTeX entry to a bibliography file:
```bash
python auto_ref.py "Attention Is All You Need" -o references.bib
```

### Batch Processing - Multiple Papers

Create a text file with paper titles (one per line):
```
# papers.txt
Attention Is All You Need
BERT: Pre-training of Deep Bidirectional Transformers
ImageNet-21K Pretraining for Semantic Segmentation
```

Process all titles in batch:
```bash
python auto_ref.py -f papers.txt
```

This generates `ref.bib` with all entries and provides a summary:
```
Found 3 titles, starting batch retrieval...

[1/3] Retrieving: Attention Is All You Need
  Successfully retrieved

[2/3] Retrieving: BERT: Pre-training of Deep Bidirectional Transformers
  Successfully retrieved

[3/3] Retrieving: ImageNet-21K Pretraining for Semantic Segmentation
  BibTeX not found

==================================================
Retrieval completed
Success: 2/3
Failed: 1/3

Failed titles:
  - ImageNet-21K Pretraining for Semantic Segmentation (Not found)
```

### Save Batch Results to Custom File

```bash
python auto_ref.py -f papers.txt -o my_references.bib
```

### Include Preprint Versions

By default, AutoRef filters out preprint versions from arXiv/CoRR, prioritizing formal conference/journal publications. Allow preprints:
```bash
python auto_ref.py "Paper Title" --allow-preprint
```

### Verbose Logging

Display detailed execution process and API interactions:
```bash
python auto_ref.py "Paper Title" -v
```

Output with verbose flag:
```
08:23:45 - [INFO] - Retrieving via DBLP engine: Paper Title
08:23:46 - [INFO] - Found target version (Venue: NeurIPS), downloading BibTeX...
08:23:47 - [INFO] - Successfully retrieved BibTeX data
```

## Command Reference

```
usage: auto_ref.py [-h] [-f FILE] [-o FILE] [--allow-preprint] [-v] [title]

positional arguments:
  title                 Full title of the paper to retrieve (wrap in quotes).
                        Or use -f to specify a text file with multiple titles.

optional arguments:
  -h, --help            Show this help message and exit
  
  -f FILE, --file FILE  Text file containing paper titles, one per line.
                        Will retrieve and generate ref.bib file.
                        
  -o FILE, --output FILE
                        Save retrieved BibTeX to specified file (example: refs.bib).
                        If not specified, print to terminal.
                        
  --allow-preprint      Allow retrieving preprint versions from arXiv/CoRR
                        (default: filter preprints, require formal conference/journal versions)
                        
  -v, --verbose         Show detailed execution process and logging information
```

## Examples

### Workflow Example 1: Building a Bibliography

```bash
# Create papers list
echo "Attention Is All You Need" > my_papers.txt
echo "BERT: Pre-training of Deep Bidirectional Transformers" >> my_papers.txt
echo "GPT-3: Language Models are Few-Shot Learners" >> my_papers.txt

# Retrieve all BibTeX entries
python auto_ref.py -f my_papers.txt -o references.bib -v

# Now references.bib contains properly formatted entries ready for LaTeX/Markdown
```

### Workflow Example 2: Quick Terminal Reference

```bash
# Quickly lookup a paper without saving
python auto_ref.py "Deep Residual Learning for Image Recognition"

# Copy the output and paste directly into your BibTeX file
```

### Workflow Example 3: Research Import from List

```bash
# Import bibliography from research template
python auto_ref.py -f related_work.txt -o chapter2_references.bib --allow-preprint
```

## Architecture

### Class Structure

```
BaseBibtexEngine (Abstract Base)
    └── DblpEngine

BibtexManager
    ├── register_engine()
    ├── get_bibtex()
    ├── _clean_and_format_bibtex()
    └── _generate_google_scholar_key()
```

### Data Flow

```
User Input (title) 
    ↓
BibtexManager.get_bibtex()
    ↓
DblpEngine.fetch_bibtex() [API call]
    ↓
BibtexManager._clean_and_format_bibtex()
    ↓
BibtexManager._generate_google_scholar_key()
    ↓
Formatted BibTeX Output
```

### Extensibility

The tool is designed for easy extension with new retrieval engines:

```python
class CustomEngine(BaseBibtexEngine):
    def fetch_bibtex(self, title: str) -> Optional[str]:
        # Your implementation
        pass

# Register in main()
manager = BibtexManager()
manager.register_engine(CustomEngine())
```

## BibTeX Processing

AutoRef performs intelligent post-processing on retrieved BibTeX:

1. **Field Normalization**: Removes redundant fields (timestamp, biburl, bibsource)
2. **Key Generation**: Creates consistent citation keys from author + year + title
3. **Author Parsing**: Intelligently handles multi-author papers and naming conventions
4. **Metadata Cleanup**: Removes OpenReview publisher entries when appropriate
5. **Whitespace Normalization**: Cleans extra spaces and line breaks

## Error Handling

### Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| `BibTeX not found` | Paper not in DBLP database | Check spelling, try full author names, use `--allow-preprint` |
| `DBLP matched no results` | Title mismatch | Use partial title, try different keywords |
| `File write failed` | Permission denied | Check file permissions, use different output path |
| `No retrieval engines registered` | Configuration error | Ensure DblpEngine is properly registered in main() |

## Performance

- **Single Paper Retrieval**: ~1-3 seconds (depends on network)
- **Batch Processing**: ~2-5 seconds per paper (with API rate limits)
- **Memory Usage**: Minimal (< 10MB)

## Limitations

- **API Dependency**: Requires network connection and DBLP API availability
- **Coverage**: Limited to papers indexed in DBLP (primarily Computer Science)
- **Accuracy**: Title must be reasonably close to official paper title
- **Rate Limiting**: Subject to DBLP API rate limits (respects delays)


## Contributing

Contributions are welcome! Areas for improvement:
- Additional retrieval engines
- Enhanced error recovery
- Performance optimization
- Test coverage expansion

## License

This project is provided as-is for academic use.

## Support

For issues, questions, or feature requests, please check the documentation or create an issue in the repository.

---

**Happy researching!** Let AutoRef handle your bibliography while you focus on the science.
