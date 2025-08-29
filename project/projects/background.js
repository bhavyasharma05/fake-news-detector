// Background service worker for Manifest V3
class FakeNewsDetector {
  constructor() {
    this.apiUrl = 'http://localhost:8000/analyze';
    this.setupEventListeners();
  }

  setupEventListeners() {
    // Listen for messages from content script
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === 'analyzeContent') {
        this.analyzeContent(request.data, sender.tab.id)
          .then(result => sendResponse({ success: true, data: result }))
          .catch(error => sendResponse({ success: false, error: error.message }));
        return true; // Keep message channel open for async response
      }
    });

    // Handle tab updates to reset badge
    chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
      if (changeInfo.status === 'loading') {
        this.resetBadge(tabId);
      }
    });
  }

  async analyzeContent(content, tabId) {
    try {
      console.log('Analyzing content:', content);
      
      const response = await fetch(this.apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(content)
      });

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`);
      }

      const result = await response.json();
      console.log('Analysis result:', result);

      // Update badge with score
      await this.updateBadge(tabId, result.score);

      // Store result for popup
      await chrome.storage.local.set({
        [`result_${tabId}`]: {
          ...result,
          url: content.url,
          timestamp: Date.now()
        }
      });

      return result;
    } catch (error) {
      console.error('Analysis failed:', error);
      await this.updateBadge(tabId, null, 'error');
      throw error;
    }
  }

  async updateBadge(tabId, score, status = 'normal') {
    let badgeText = '';
    let badgeColor = '#gray';

    if (status === 'error') {
      badgeText = '!';
      badgeColor = '#666';
    } else if (score !== null) {
      badgeText = score.toString();
      
      if (score >= 70) {
        badgeColor = '#22C55E'; // Green - Reliable
      } else if (score >= 40) {
        badgeColor = '#F59E0B'; // Yellow - Suspicious
      } else {
        badgeColor = '#EF4444'; // Red - Fake
      }
    }

    await chrome.action.setBadgeText({ tabId, text: badgeText });
    await chrome.action.setBadgeBackgroundColor({ tabId, color: badgeColor });
  }

  async resetBadge(tabId) {
    await chrome.action.setBadgeText({ tabId, text: '' });
  }
}

// Initialize the detector
new FakeNewsDetector();