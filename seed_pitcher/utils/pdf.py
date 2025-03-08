"""PDF processing utilities for extracting text from pitch decks."""

from pathlib import Path
from typing import Optional


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF file (pitch deck)."""
    try:
        from pypdf import PdfReader

        # Initialize PDF reader
        reader = PdfReader(pdf_path)
        text = ""

        # Extract text from each page
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"

        return text
    except ImportError:
        print("PyPDF not installed. Please install it with: pip install pypdf")
        return ""
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return ""
