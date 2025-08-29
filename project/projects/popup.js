// Popup script for displaying analysis results
class PopupController {
  constructor() {
    this.elements = this.initializeElements();
    this.init();
  }

  initializeElements() {
    return {
      loading: document.getElementById('loading'),
      noAnalysis: document.getElementById('no-analysis'),
      error: document.getElementById('error'),
      errorMessage: document.getElementById('error-message'),
      results: document.getElementById('results'),
      scoreValue: document.getElementById('score-value'),
      scoreLabel: document.getElementById('score-label'),
      scoreDescription: document.getElementById('score-description'),
      explanations: document.getElementById('explanations'),
      evidenceSection: document.getElementById('evidence-section'),
      evidenceLinks: document.getElementById('evidence-links'),
      analyzedUrl: document.getElementById('analyzed-url'),
      analysisTime: document.getElementById('analysis-time'),
      refreshBtn: document.getElementById('refresh-btn')
    };
  }

  async init() {
    // Set up event listeners
    this.elements.refreshBtn.addEventListener('click', () => this.refreshAnalysis());

    // Load and display results
    await this.loadResults();
  }

  async loadResults() {
    try {
      // Get current tab
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab) {
        this.showError('Unable to access current tab');
        return;
      }

      // Get stored result for this tab
      const result = await chrome.storage.local.get(`result_${tab.id}`);
      const analysisData = result[`result_${tab.id}`];

      if (analysisData) {
        this.displayResults(analysisData);
      } else {
        this.showNoAnalysis();
      }
    } catch (error) {
      console.error('Failed to load results:', error);
      this.showError('Failed to load analysis results');
    }
  }

  displayResults(data) {
    this.hideAllSections();
    this.elements.results.classList.remove('hidden');

    // Update score
    this.elements.scoreValue.textContent = data.score;
    this.elements.scoreLabel.textContent = data.label;

    // Update score circle color and description
    const scoreCircle = document.querySelector('.score-circle');
    let description = '';
    
    if (data.score >= 70) {
      scoreCircle.className = 'score-circle reliable';
      description = 'This content appears to be reliable and trustworthy.';
    } else if (data.score >= 40) {
      scoreCircle.className = 'score-circle suspicious';
      description = 'This content should be verified before sharing.';
    } else {
      scoreCircle.className = 'score-circle fake';
      description = 'This content appears to contain false information.';
    }
    
    this.elements.scoreDescription.textContent = description;

    // Display explanations
    this.displayExplanations(data.explanations);

    // Display evidence links
    this.displayEvidenceLinks(data.evidence_links);

    // Update meta information
    this.elements.analyzedUrl.href = data.url;
    this.elements.analyzedUrl.textContent = this.truncateUrl(data.url);
    this.elements.analysisTime.textContent = `Analysis time: ${this.formatTimestamp(data.timestamp)}`;
  }

  displayExplanations(explanations) {
    this.elements.explanations.innerHTML = '';
    
    if (!explanations || explanations.length === 0) {
      this.elements.explanations.innerHTML = '<p class="no-data">No detailed explanations available.</p>';
      return;
    }

    explanations.forEach(explanation => {
      const explanationEl = document.createElement('div');
      explanationEl.className = 'explanation-item';
      explanationEl.innerHTML = `
        <div class="explanation-icon">${this.getExplanationIcon(explanation.type)}</div>
        <div class="explanation-content">
          <strong>${explanation.title}</strong>
          <p>${explanation.description}</p>
        </div>
      `;
      this.elements.explanations.appendChild(explanationEl);
    });
  }

  displayEvidenceLinks(evidenceLinks) {
    if (!evidenceLinks || evidenceLinks.length === 0) {
      this.elements.evidenceSection.classList.add('hidden');
      return;
    }

    this.elements.evidenceSection.classList.remove('hidden');
    this.elements.evidenceLinks.innerHTML = '';

    evidenceLinks.forEach(link => {
      const linkEl = document.createElement('a');
      linkEl.href = link.url;
      linkEl.target = '_blank';
      linkEl.className = 'evidence-link';
      linkEl.innerHTML = `
        <div class="evidence-icon">🔗</div>
        <div class="evidence-content">
          <strong>${link.source}</strong>
          <p>${link.description}</p>
        </div>
        <div class="external-icon">↗</div>
      `;
      this.elements.evidenceLinks.appendChild(linkEl);
    });
  }

  getExplanationIcon(type) {
    const icons = {
      'source': '📰',
      'language': '🗣️',
      'bias': '⚖️',
      'factcheck': '✓',
      'sentiment': '😐',
      'default': '💡'
    };
    return icons[type] || icons.default;
  }

  showNoAnalysis() {
    this.hideAllSections();
    this.elements.noAnalysis.classList.remove('hidden');
  }

  showError(message) {
    this.hideAllSections();
    this.elements.errorMessage.textContent = message;
    this.elements.error.classList.remove('hidden');
  }

  showLoading() {
    this.hideAllSections();
    this.elements.loading.classList.remove('hidden');
  }

  hideAllSections() {
    [this.elements.loading, this.elements.noAnalysis, this.elements.error, this.elements.results]
      .forEach(el => el.classList.add('hidden'));
  }

  async refreshAnalysis() {
    this.showLoading();
    
    try {
      // Get current tab
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab) {
        this.showError('Unable to access current tab');
        return;
      }

      // Inject content script to re-analyze
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          // Trigger re-analysis by dispatching a custom event
          window.dispatchEvent(new Event('refreshAnalysis'));
        }
      });

      // Wait a moment then reload results
      setTimeout(() => this.loadResults(), 2000);
      
    } catch (error) {
      console.error('Refresh failed:', error);
      this.showError('Failed to refresh analysis');
    }
  }

  truncateUrl(url) {
    if (url.length <= 50) return url;
    const urlObj = new URL(url);
    return `${urlObj.hostname}${urlObj.pathname.substring(0, 20)}...`;
  }

  formatTimestamp(timestamp) {
    return new Date(timestamp).toLocaleString();
  }
}

// Initialize popup when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  new PopupController();
});

document.getElementById('analyze-btn').addEventListener('click', async () => {
    const text = document.getElementById('snippet-input').value.trim();
    if (!text) {
        showError('Please enter or select some text to analyze.');
        return;
    }
    showLoader();
    try {
        const url = window.location.href;
        const response = await fetch('http://localhost:8000/api/fakenews/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, url })
        });
        if (response.ok) {
            const data = await response.json();
            showAnalysis({ ...data, url });
        } else {
            const err = await response.json();
            showError(err.detail || 'Analysis failed.');
        }
    } catch (e) {
        showError('Unable to connect to backend.');
    }
});

document.getElementById('auto-btn').addEventListener('click', async () => {
    showLoader();
    // Ask content script to extract main text from the page
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
        chrome.tabs.sendMessage(tabs[0].id, {action: "extractMainText"}, async function(response) {
            if (chrome.runtime.lastError) {
                showError('Unable to connect to content script. Try reloading the page.');
                return;
            }
            const text = response && response.text ? response.text.trim() : "";
            if (!text) {
                showError('Unable to extract main content from this page.');
                return;
            }
            try {
                const url = tabs[0].url;
                const res = await fetch('http://localhost:8000/api/fakenews/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text, url })
                });
                if (res.ok) {
                    const data = await res.json();
                    showAnalysis({ ...data, url });
                } else {
                    const err = await res.json();
                    showError(err.detail || 'Analysis failed.');
                }
            } catch (e) {
                showError('Unable to connect to backend.');
            }
        });
    });
});

function showLoader() {
    const loader = document.getElementById('loader');
    const analysisCard = document.getElementById('analysis-card');
    const errorCard = document.getElementById('error-card');
    if (loader) loader.style.display = 'block';
    if (analysisCard) analysisCard.classList.add('hidden');
    if (errorCard) errorCard.classList.add('hidden');
}

function showAnalysis(data) {
    const loader = document.getElementById('loader');
    const analysisCard = document.getElementById('analysis-card');
    const errorCard = document.getElementById('error-card');
    if (loader) loader.style.display = 'none';
    if (analysisCard) {
        analysisCard.classList.remove('hidden');
        analysisCard.style.animation = 'fadeIn 0.7s';
        document.getElementById('score').textContent = `${data.credibility_score} /100`;
        document.getElementById('label').textContent = data.label;
        document.getElementById('label').className = `label ${data.label}`;
        document.getElementById('explanation').textContent = data.explanation;
        document.getElementById('url').textContent = `Analyzed URL: ${data.url}`;
        document.getElementById('timestamp').textContent = `Analysis time: ${new Date().toLocaleString()}`;
        // Sources
        const sourcesDiv = document.getElementById('sources');
        sourcesDiv.innerHTML = '';
        if (data.sources && data.sources.length > 0) {
            data.sources.forEach(src => {
                const el = document.createElement('div');
                el.className = 'source-item';
                el.innerHTML = `<strong>${src.title}</strong><br>
                    <a href="${src.url}" target="_blank">${src.url}</a><br>
                    <span>${src.snippet}</span>`;
                sourcesDiv.appendChild(el);
            });
        }
    }
    if (errorCard) errorCard.classList.add('hidden');
}

function showError(msg) {
    const loader = document.getElementById('loader');
    const analysisCard = document.getElementById('analysis-card');
    const errorCard = document.getElementById('error-card');
    if (loader) loader.style.display = 'none';
    if (analysisCard) analysisCard.classList.add('hidden');
    if (errorCard) {
        errorCard.classList.remove('hidden');
        const errorMsg = document.getElementById('error-message');
        if (errorMsg) errorMsg.textContent = msg;
    }
}