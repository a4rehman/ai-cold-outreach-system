# 🚀 AI-Powered Salon Lead Generation System

A professional, LangGraph-orchestrated pipeline for discovering beauty salons, analyzing their digital presence with AI, and automating personalized cold outreach.

## 📁 Project Structure

```text
cold_mail/
├── data/               # Persistent storage for results and memory
│   ├── lead_gen_results.json
│   ├── leads_for_google_sheets.csv
│   └── processed_leads.json
├── docs/               # Documentation and workflow graphs
│   ├── workflow_graph.mmd
│   └── workflow_graph.png
├── src/                # Core application logic
│   └── lead_gen.py
├── main.py             # Entry point
├── .env                # API keys and credentials (ignored by git)
├── .gitignore          # Git exclusion rules
└── requirements.txt    # Project dependencies
```

## 🛠 Features

- **Automated Discovery**: Uses Playwright to scan Google Maps for beauty salons in target cities.
- **Intelligent Scraping**: Extracts text and email addresses from salon websites.
- **AI Analysis**: Uses GPT-4o-mini to analyze the business and draft personalized emails.
- **Email Automation**: (Optional) Sends emails directly via SMTP.
- **Robust Orchestration**: Powered by LangGraph for state management and retry logic.
- **Progressive Saving**: Updates JSON and CSV outputs in real-time.

## 🚀 Getting Started

1.  **Clone & Install**:
    ```bash
    pip install -r requirements.txt
    playwright install chromium
    ```

2.  **Configuration**:
    Create a `.env` file in the root with:
    ```env
    OPENAI_API_KEY=your_key_here
    # SMTP Config (Optional for sending emails)
    EMAIL_USER=your_email@gmail.com
    EMAIL_PASSWORD=your_app_password
    ```

3.  **Run the Pipeline**:
    ```bash
    python main.py
    ```

## 📊 Output
- Results are saved to `data/lead_gen_results.json`.
- A CSV ready for Google Sheets is generated at `data/leads_for_google_sheets.csv`.
- Processed URLs are stored in `data/processed_leads.json` to avoid duplicates in future runs.
