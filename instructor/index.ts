import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

// ============================================================================
// Configuration
// ============================================================================

const config = new pulumi.Config();
const workshopTitle = config.get("workshopTitle") || "Workshop Credentials";
const values = config.requireObject<Record<string, string>>("values");

// ============================================================================
// Generate HTML
// ============================================================================

function generateHtml(
  title: string,
  kvPairs: Record<string, string>,
): string {
  const cards = Object.entries(kvPairs)
    .map(
      ([key, value]) => `
        <div class="card group" data-value="${value.replace(/"/g, "&quot;")}">
          <div class="card-label">${key}</div>
          <div class="card-value-row">
            <code class="card-value" title="${value.replace(/"/g, "&quot;")}">${value}</code>
            <button class="copy-btn" onclick="copyValue(this)" aria-label="Copy ${key}">
              <svg class="icon-copy" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              <svg class="icon-check hidden" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </button>
          </div>
        </div>`,
    )
    .join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg: #0a0a0f;
      --surface: #12121a;
      --surface-hover: #1a1a26;
      --border: #2a2a3a;
      --border-accent: #6366f1;
      --text: #e4e4ed;
      --text-dim: #8888a0;
      --accent: #6366f1;
      --accent-glow: rgba(99, 102, 241, 0.15);
      --success: #22c55e;
      --font-body: 'Instrument Sans', system-ui, sans-serif;
      --font-mono: 'DM Mono', 'SF Mono', monospace;
    }

    body {
      font-family: var(--font-body);
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }

    /* Subtle grid background */
    body::before {
      content: '';
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(99, 102, 241, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(99, 102, 241, 0.03) 1px, transparent 1px);
      background-size: 60px 60px;
      pointer-events: none;
      z-index: 0;
    }

    .container {
      position: relative;
      z-index: 1;
      max-width: 720px;
      margin: 0 auto;
      padding: 80px 24px 60px;
    }

    @media (max-width: 640px) {
      .container { padding: 40px 16px 40px; }
    }

    /* Header */
    .header {
      margin-bottom: 56px;
      text-align: center;
    }

    .badge {
      display: inline-block;
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--accent);
      background: var(--accent-glow);
      border: 1px solid rgba(99, 102, 241, 0.25);
      border-radius: 100px;
      padding: 6px 16px;
      margin-bottom: 24px;
    }

    h1 {
      font-size: clamp(1.5rem, 4vw, 2rem);
      font-weight: 700;
      letter-spacing: -0.02em;
      line-height: 1.2;
      color: #fff;
      margin-bottom: 12px;
    }

    .subtitle {
      font-size: 15px;
      color: var(--text-dim);
      line-height: 1.5;
    }

    /* Cards */
    .cards {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px 24px;
      transition: border-color 0.2s, background 0.2s;
    }

    .card:hover {
      border-color: var(--border-accent);
      background: var(--surface-hover);
    }

    .card-label {
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-dim);
      margin-bottom: 10px;
    }

    .card-value-row {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .card-value {
      flex: 1;
      font-family: var(--font-mono);
      font-size: 14px;
      font-weight: 400;
      color: var(--text);
      word-break: break-all;
      line-height: 1.5;
      background: none;
      padding: 0;
    }

    .copy-btn {
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: transparent;
      color: var(--text-dim);
      cursor: pointer;
      transition: all 0.15s;
    }

    .copy-btn:hover {
      color: var(--accent);
      border-color: var(--accent);
      background: var(--accent-glow);
    }

    .copy-btn.copied {
      color: var(--success);
      border-color: var(--success);
      background: rgba(34, 197, 94, 0.1);
    }

    .hidden { display: none; }

    /* Toast */
    .toast {
      position: fixed;
      bottom: 32px;
      left: 50%;
      transform: translateX(-50%) translateY(20px);
      font-family: var(--font-mono);
      font-size: 13px;
      color: var(--success);
      background: #0f1f15;
      border: 1px solid rgba(34, 197, 94, 0.3);
      border-radius: 8px;
      padding: 10px 20px;
      opacity: 0;
      transition: opacity 0.2s, transform 0.2s;
      pointer-events: none;
      z-index: 100;
    }

    .toast.show {
      opacity: 1;
      transform: translateX(-50%) translateY(0);
    }

    /* Footer */
    .footer {
      margin-top: 56px;
      text-align: center;
      font-size: 13px;
      color: var(--text-dim);
    }

    .footer a {
      color: var(--accent);
      text-decoration: none;
    }

    .footer a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <header class="header">
      <div class="badge">Workshop Credentials</div>
      <h1>${title}</h1>
      <p class="subtitle">Click the copy button next to any value to copy it to your clipboard.</p>
    </header>

    <div class="cards">
      ${cards}
    </div>

    <footer class="footer">
      Powered by <a href="https://www.pulumi.com" target="_blank">Pulumi</a> &middot; Values served from Pulumi ESC
    </footer>
  </div>

  <div class="toast" id="toast">Copied to clipboard</div>

  <script>
    function copyValue(btn) {
      const card = btn.closest('.card');
      const value = card.dataset.value;
      navigator.clipboard.writeText(value).then(() => {
        // Button feedback
        const iconCopy = btn.querySelector('.icon-copy');
        const iconCheck = btn.querySelector('.icon-check');
        iconCopy.classList.add('hidden');
        iconCheck.classList.remove('hidden');
        btn.classList.add('copied');

        // Toast
        const toast = document.getElementById('toast');
        const label = card.querySelector('.card-label').textContent;
        toast.textContent = label + ' copied!';
        toast.classList.add('show');

        setTimeout(() => {
          iconCopy.classList.remove('hidden');
          iconCheck.classList.add('hidden');
          btn.classList.remove('copied');
          toast.classList.remove('show');
        }, 2000);
      });
    }
  </script>
</body>
</html>`;
}

// ============================================================================
// S3 Bucket (private, CloudFront origin)
// ============================================================================

const siteBucket = new aws.s3.Bucket("site", {
  bucketPrefix: "workshop-instructor-",
  forceDestroy: true,
  tags: { Name: "workshop-instructor-site", Purpose: "Instructor credential sharing" },
});

new aws.s3.BucketPublicAccessBlock("site", {
  bucket: siteBucket.id,
  blockPublicAcls: true,
  blockPublicPolicy: true,
  ignorePublicAcls: true,
  restrictPublicBuckets: true,
});

// ============================================================================
// Generate and upload HTML
// ============================================================================

const htmlContent = generateHtml(workshopTitle, values);

const indexHtml = new aws.s3.BucketObjectv2("index", {
  bucket: siteBucket.id,
  key: "index.html",
  content: htmlContent,
  contentType: "text/html",
  tags: { Name: "instructor-index-html" },
});

// ============================================================================
// CloudFront Origin Access Control
// ============================================================================

const oac = new aws.cloudfront.OriginAccessControl("site", {
  name: "workshop-instructor-oac",
  description: "OAC for instructor credential site",
  originAccessControlOriginType: "s3",
  signingBehavior: "always",
  signingProtocol: "sigv4",
});

// ============================================================================
// CloudFront Distribution
// ============================================================================

// Use AWS managed CachingOptimized policy instead of deprecated forwardedValues
const cachingOptimized = aws.cloudfront.getCachePolicyOutput({
  name: "Managed-CachingOptimized",
});

const distribution = new aws.cloudfront.Distribution("site", {
  enabled: true,
  defaultRootObject: "index.html",
  comment: "Workshop instructor credential sharing site",
  origins: [
    {
      domainName: siteBucket.bucketRegionalDomainName,
      originId: "s3-origin",
      originAccessControlId: oac.id,
    },
  ],
  defaultCacheBehavior: {
    targetOriginId: "s3-origin",
    viewerProtocolPolicy: "redirect-to-https",
    allowedMethods: ["GET", "HEAD"],
    cachedMethods: ["GET", "HEAD"],
    cachePolicyId: cachingOptimized.apply((p) => p.id!),
    compress: true,
  },
  restrictions: {
    geoRestriction: { restrictionType: "none" },
  },
  viewerCertificate: {
    cloudfrontDefaultCertificate: true,
  },
  tags: { Name: "workshop-instructor-distribution" },
});

// ============================================================================
// S3 Bucket Policy (allow CloudFront via OAC)
// ============================================================================

new aws.s3.BucketPolicy("site", {
  bucket: siteBucket.id,
  policy: pulumi
    .all([siteBucket.arn, distribution.arn])
    .apply(([bucketArn, distArn]) =>
      JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Sid: "AllowCloudFrontOAC",
            Effect: "Allow",
            Principal: { Service: "cloudfront.amazonaws.com" },
            Action: "s3:GetObject",
            Resource: `${bucketArn}/*`,
            Condition: {
              StringEquals: { "AWS:SourceArn": distArn },
            },
          },
        ],
      }),
    ),
});

// ============================================================================
// Outputs
// ============================================================================

export const siteUrl = pulumi.interpolate`https://${distribution.domainName}`;
export const distributionId = distribution.id;
export const bucketName = siteBucket.id;
