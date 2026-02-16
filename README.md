# Company Description Enricher

## Overview

**Company Description Enricher** is a lightweight data enrichment tool developed as part of the **SSC project for BFH**.
The application automates the process of collecting and normalizing concise company descriptions based on publicly available website content.

The tool is designed to support research and data preparation workflows by reducing manual effort in maintaining up-to-date, consistent “solution descriptions” for companies in a structured database.

---

## Problem Statement

Maintaining high-quality company descriptions in business or research databases is time-consuming and error-prone when done manually.
Typical challenges include:

* Inconsistent writing style and level of detail across entries
* Outdated or missing descriptions
* Manual copy-pasting from websites, which does not scale
* Difficulty tracking which websites failed to load or provide usable content

This application addresses these issues by:

* Automatically extracting relevant information from company websites
* Normalizing descriptions into a concise, database-friendly format
* Providing transparency into extraction errors and edge cases
* Optionally enhancing the baseline descriptions with an LLM for improved clarity

---

## Scope within the SSC Project (BFH)

Within the SSC project at BFH, this tool serves as a **data enrichment and preparation component**.
It is used to:

* Prepare structured datasets for analysis and reporting
* Improve the quality and consistency of company metadata
* Support downstream workflows that depend on reliable company descriptions

The application is intentionally kept modular and lightweight so that it can be integrated into broader data processing pipelines or used as a standalone utility.

---

## Technical Architecture (High-Level)

At a high level, the application implements the following pipeline:

1. **Input**
   An Excel file with a `Database` sheet containing at least:

   * `Company`
   * `Website`

2. **Web Extraction (Scraper Layer)**

   * Fetches the company website
   * Attempts to extract a concise description from:

     * Open Graph / meta description
     * JSON-LD structured data
     * Main page content (fallback via content extraction)

3. **Optional LLM Enhancement (Enrichment Layer)**

   * The extracted baseline description is optionally sent to an LLM
   * The LLM normalizes and condenses the text into a short, neutral “solution description”
   * If the LLM is unavailable or fails, the system falls back to the scraper result

4. **Output**

   * Enriched Excel file with a normalized `Description` column
   * Separate technical error overview for transparency (e.g., timeouts, blocked websites)

The design ensures that the scraper remains the primary data source, while the LLM acts as a non-blocking enhancement step.

---

## Technology Stack

### Language

* **Python**
  Chosen for its strong ecosystem in data processing, web scraping, and rapid prototyping.

### Libraries and Frameworks

* **Streamlit**
  Used to provide a simple, user-friendly web interface for non-technical users.

* **pandas**
  For reading, transforming, and writing Excel data in a structured and reliable way.

* **httpx**
  HTTP client for robust and configurable website requests.

* **BeautifulSoup (bs4)**
  For parsing HTML and extracting metadata such as meta descriptions and Open Graph tags.

* **trafilatura**
  For extracting the main textual content from web pages when metadata is not available.

* **python-dotenv**
  For local environment configuration (API keys, model selection).

* **OpenAI API (optional)**
  Used as an enrichment layer to normalize and improve textual descriptions.
  The system is designed to degrade gracefully if the LLM is unavailable.

---

## How It Works (IT Perspective)

* The application processes the input row by row.
* For each company:

  * A single HTTP request is performed to retrieve website content.
  * A prioritized extraction strategy is applied (meta → structured data → main content).
  * The extracted text is normalized and optionally refined by an LLM.
* Errors (e.g., HTTP 403, timeouts) are captured and exposed in the UI for auditability.
* The final Excel output contains only business-relevant columns, while technical details remain in the UI layer.

The architecture deliberately separates:

* **Data extraction**
* **Optional AI-based enrichment**
* **User interface**
* **Export logic**

This keeps the system maintainable and extensible.

---

## Running Locally

### Prerequisites

* Python 3.10+
* Virtual environment recommended

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment Configuration (Optional LLM)

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-5-mini
```

If no API key is provided, the application will run in **scraper-only mode**.

### Run the Application

```bash
streamlit run streamlit_app.py
```

Open the provided local URL in your browser, upload the Excel file, and start the enrichment process.

---

## Design Principles

* **Resilience by Design**
  External dependencies (LLM, websites) are treated as unreliable. Failures do not break the pipeline.

* **Transparency**
  All extraction and enrichment issues are visible to the user.

* **Minimal Coupling**
  The LLM is an optional enhancement, not a hard dependency.

* **Reproducibility**
  Given the same input and environment, the scraper layer produces deterministic results.

---

## Future Improvements (Outlook)

* Structured logging and centralized monitoring
* Batch processing and scheduling for periodic updates
* Language detection and multilingual support
* Configurable enrichment policies (e.g., strict scraper-only mode vs. AI-enhanced mode)

---

