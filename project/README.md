# Fake News Detector Chrome Extension

A Chrome Browser Extension (Manifest V3) that analyzes webpage content for fake news indicators and provides credibility scoring with explanations.

## Features

- 🔍 **Real-time Content Analysis**: Automatically extracts and analyzes article content
- 📊 **Credibility Scoring**: Provides scores from 0-100 with color-coded labels
- 🎯 **Visual Feedback**: Badge icons show credibility status (green/yellow/red)
- 📋 **Detailed Reports**: Popup interface with explanations and fact-check sources
- 🔄 **Refresh Analysis**: Re-analyze content on demand
- 💾 **Result Caching**: Stores analysis results locally

## Installation

### 1. Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Start the FastAPI Backend

```bash
cd backend
python main.py
```

The API will be available at `http://localhost:8000`

### 3. Load Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" in the top right
3. Click "Load unpacked" and select the extension directory
4. The extension should now appear in your browser toolbar

## Usage

1. Navigate to any news article or webpage
2. The extension automatically extracts and analyzes the content
3. Check the badge icon for quick credibility status:
   - **Green (70-100)**: Reliable ✅
   - **Yellow (40-69)**: Suspicious ⚠️
   - **Red (0-39)**: Fake ❌
4. Click the extension icon to view detailed analysis results
5. Use the "Refresh Analysis" button to re-analyze content

## API Endpoints

### POST /analyze
Analyzes content for fake news indicators.

**Request:**
```json
{
  "title": "Article title",
  "content": "Article body content...",
  "url": "https://example.com/article"
}
```

**Response:**
```json
{
  "score": 75,
  "label": "Reliable ✅",
  "explanations": [
    {
      "type": "source",
      "title": "Recognized News Source",
      "description": "Content from reliable news organization"
    }
  ],
  "evidence_links": [
    {
      "source": "Snopes",
      "url": "https://www.snopes.com/fact-check/",
      "description": "Fact-checking database"
    }
  ]
}
```

### GET /health
Health check endpoint for monitoring API status.

## Development

### Extension Structure

```
├── manifest.json          # Extension configuration (Manifest V3)
├── background.js          # Service worker for API calls and badge updates
├── contentScript.js       # Content extraction from webpages
├── popup.html            # Extension popup interface
├── popup.js              # Popup functionality and result display
├── styles.css            # Popup styling
└── backend/
    ├── main.py           # FastAPI server with analysis logic
    └── requirements.txt  # Python dependencies
```

### Analysis Algorithm

The current implementation uses rule-based analysis examining:

- **Title Analysis**: Sensationalized language, excessive caps, suspicious keywords
- **Content Quality**: Length, emotional language, professional terminology
- **Source Analysis**: Domain reputation and recognition
- **Language Patterns**: Professional vs. sensationalized writing style

*Note: This is a demonstration implementation. Production systems would use sophisticated ML models trained on large datasets of verified fake and real news.*

## Customization

### Adding New Analysis Rules

Edit `backend/main.py` in the `FakeNewsAnalyzer` class:

```python
def _analyze_title(self, title: str) -> int:
    # Add custom title analysis rules
    score = 0
    # Your custom logic here
    return score
```

### Modifying UI

Edit `styles.css` and `popup.html` to customize the extension appearance.

### Extending API

Add new endpoints in `backend/main.py`:

```python
@app.post("/custom-endpoint")
async def custom_analysis(request: CustomRequest):
    # Your custom analysis logic
    return response
```

## Security Considerations

- API calls are made over HTTP for development; use HTTPS in production
- Content is analyzed locally and via API; ensure data privacy compliance
- Extension requests permissions for active tabs only
- All external links open in new tabs for security

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with the Chrome extension
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- Check the Chrome extension console for errors
- Verify the FastAPI backend is running on port 8000
- Check browser permissions for the extension
- Review the API documentation at `http://localhost:8000/docs`