// Universium — Service Worker
importScripts('/uv/uv.bundle.js');
importScripts('/uv/uv.config.js');
importScripts('/uv/uv.sw.js');

const sw = new UVServiceWorker();

// ── Ad/Tracker blocklist ──────────────────────────────────────────────────
// Matches against the decoded destination URL inside UV-proxied requests
const AD_PATTERNS = [
  // Google Ads / DoubleClick
  'googlesyndication.com', 'doubleclick.net', 'googleadservices.com',
  'google-analytics.com', 'googletagmanager.com', 'googletagservices.com',
  // Meta / Facebook pixel
  'facebook.net/en_US/fbevents', 'connect.facebook.net',
  // Amazon Ads
  'amazon-adsystem.com', 'assoc-amazon.com',
  // Common ad networks
  'ads.twitter.com', 'static.ads-twitter.com',
  'adnxs.com', 'adsafeprotected.com', 'adsrvr.org',
  'advertising.com', 'adform.net', 'adf.ly',
  'outbrain.com', 'taboola.com', 'revcontent.com',
  'moatads.com', 'scorecardresearch.com',
  'criteo.com', 'criteo.net',
  'rubiconproject.com', 'pubmatic.com', 'openx.net',
  'casalemedia.com', 'contextweb.com',
  'adsystem.amazon', 'media.net',
  // Analytics / Trackers
  'hotjar.com', 'fullstory.com', 'mouseflow.com',
  'segment.com', 'mixpanel.com', 'heap.io',
  'pardot.com', 'marketo.net',
  // CDN-hosted ad scripts
  'pagead2.googlesyndication', 'tpc.googlesyndication',
  // Misc
  'adroll.com', 'quantserve.com', 'zedo.com',
  'bidswitch.net', 'sharethrough.com', 'spotxchange.com',
  'lijit.com', 'sovrn.com', '33across.com',
];

function isAd(url) {
  try {
    const u = url.toLowerCase();
    return AD_PATTERNS.some(p => u.includes(p));
  } catch(_) { return false; }
}

// Read adblock preference from cookie (SW can't access localStorage)
function adblockEnabled() {
  // Default on — SW uses cookies to read the setting
  // We store it as a simple cookie: uos-adblock=1 or uos-adblock=0
  // Falls back to true if no cookie found
  try {
    const m = (self._adblock !== undefined) ? self._adblock : true;
    return m;
  } catch(_) { return true; }
}

// Listen for messages from the page to toggle adblock
self.addEventListener('message', e => {
  if (e.data?.type === 'SET_ADBLOCK') {
    self._adblock = e.data.value;
  }
});

self.addEventListener('fetch', event => {
  event.respondWith(
    (async () => {
      if (sw.route(event)) {
        // Decode the proxied URL to check for ads
        try {
          const uvUrl = __uv$config.decodeUrl(
            event.request.url.slice(
              event.request.url.indexOf(__uv$config.prefix) + __uv$config.prefix.length
            )
          );
          if (adblockEnabled() && isAd(uvUrl)) {
            // Return empty 200 response — invisible to the page
            return new Response('', {
              status: 200,
              headers: { 'Content-Type': 'text/plain' }
            });
          }
        } catch(_) {}
        return await sw.fetch(event);
      }
      return await fetch(event.request);
    })()
  );
});
