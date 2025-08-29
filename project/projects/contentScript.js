// Content script to extract article content and trigger analysis
class ContentExtractor {
  constructor() {
    this.minContentLength = 200; // Minimum content length to analyze
    this.init();
  }

  init() {
    // Wait for page to load completely
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.extractAndAnalyze());
    } else {
      this.extractAndAnalyze();
    }
  }

  extractContent() {
    const content = {
      title: this.extractTitle(),
      content: this.extractArticleContent(),
      url: window.location.href
    };

    console.log('Extracted content:', content);
    return content;
  }

  extractTitle() {
    // Try multiple selectors for title
    const titleSelectors = [
      'h1[class*="title"]',
      'h1[class*="headline"]', 
      '.article-title',
      '.post-title',
      'h1',
      'title'
    ];

    for (const selector of titleSelectors) {
      const element = document.querySelector(selector);
      if (element && element.textContent.trim()) {
        return element.textContent.trim();
      }
    }

    // Fallback to document title
    return document.title || '';
  }

  extractArticleContent() {
    // Try to find main article content
    const contentSelectors = [
      'article',
      '[role="main"]',
      '.article-content',
      '.post-content',
      '.entry-content',
      '.content',
      'main'
    ];

    let content = '';

    for (const selector of contentSelectors) {
      const element = document.querySelector(selector);
      if (element) {
        content = this.cleanText(element.textContent || '');
        if (content.length > this.minContentLength) {
          break;
        }
      }
    }

    // Fallback to body if no specific content found
    if (content.length < this.minContentLength) {
      content = this.cleanText(document.body.textContent || '');
    }

    return content;
  }

  cleanText(text) {
    return text
      .replace(/\s+/g, ' ') // Normalize whitespace
      .replace(/\n+/g, ' ') // Remove line breaks
      .trim()
      .substring(0, 5000); // Limit content length
  }

  async extractAndAnalyze() {
    try {
      // Skip non-article pages
      if (this.shouldSkipPage()) {
        return;
      }

      const content = this.extractContent();

      // Only analyze if we have sufficient content
      if (content.content.length < this.minContentLength) {
        console.log('Content too short for analysis');
        return;
      }

      // Send to background script for analysis
      chrome.runtime.sendMessage({
        action: 'analyzeContent',
        data: content
      }, (response) => {
        if (chrome.runtime.lastError) {
          console.error('Message sending failed:', chrome.runtime.lastError);
          return;
        }

        if (response && response.success) {
          console.log('Analysis completed:', response.data);
        } else if (response && response.error) {
          console.error('Analysis failed:', response.error);
        }
      });

    } catch (error) {
      console.error('Content extraction failed:', error);
    }
  }

  shouldSkipPage() {
    const url = window.location.href;
    const skipPatterns = [
      /^chrome-extension:/,
      /^chrome:/,
      /^about:/,
      /\.(pdf|jpg|png|gif|mp4|mp3)$/i,
      /google\.com\/search/,
      /youtube\.com\/watch/
    ];

    return skipPatterns.some(pattern => pattern.test(url));
  }
}

// Initialize content extractor
new ContentExtractor();

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "extractMainText") {
        let text = "";
        // Try <article>
        const article = document.querySelector('article');
        if (article && article.innerText.trim().length > 100) {
            text = article.innerText;
        } else {
            // Try common main content containers
            const main = document.querySelector('main');
            if (main && main.innerText.trim().length > 100) {
                text = main.innerText;
            } else {
                const selectors = [
                    '[role="main"]',
                    '.main-content',
                    '.content',
                    '.post-content',
                    '.entry-content',
                    '.article-content',
                    '.story-content',
                    '.news-content',
                    '.body-content'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText.trim().length > 100) {
                        text = el.innerText;
                        break;
                    }
                }
                // Fallback: get largest visible block of text
                if (!text) {
                    let allElements = Array.from(document.body.querySelectorAll('*'));
                    let largest = '';
                    allElements.forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (
                            el.innerText &&
                            el.innerText.trim().length > largest.length &&
                            style.display !== 'none' &&
                            style.visibility !== 'hidden'
                        ) {
                            largest = el.innerText.trim();
                        }
                    });
                    text = largest;
                }
                // Final fallback: get largest <p> blocks
                if (!text) {
                    let paragraphs = Array.from(document.querySelectorAll('p'));
                    if (paragraphs.length > 0) {
                        paragraphs.sort((a, b) => b.innerText.length - a.innerText.length);
                        text = paragraphs.slice(0, 5).map(p => p.innerText).join('\n\n');
                    }
                }
            }
        }
        sendResponse({text});
    }
    return true; // Needed for async sendResponse
});