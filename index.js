/**
 * Cloudflare Worker: Product Crawler
 * Uses Cloudflare's global edge network to bypass blocks
 */

const TARGET_HOST = 'www.omc-stepperonline.com';

export default {
  async fetch(request, env, ctx) {
    // Only allow POST
    if (request.method !== 'POST') {
      return new Response(JSON.stringify({ error: 'Method not allowed' }), {
        status: 405,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    try {
      const { url } = await request.json();

      if (!url || !url.includes(TARGET_HOST)) {
        return new Response(JSON.stringify({ error: 'Invalid URL' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        });
      }

      // Fetch with browser-like headers
      const response = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
          'Accept-Language': 'en-US,en;q=0.9',
          'Accept-Encoding': 'gzip, deflate',
          'Connection': 'keep-alive',
          'Upgrade-Insecure-Requests': '1',
          'Cache-Control': 'no-cache',
        }
      });

      if (response.status === 403) {
        return new Response(JSON.stringify({ error: '403 Forbidden' }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' }
        });
      }

      const html = await response.text();
      const productData = parseProductHTML(html, url);

      return new Response(JSON.stringify(productData), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }
};

function parseProductHTML(html, url) {
  const data = {
    url,
    name: '',
    sku: '',
    price: '',
    description: '',
    specifications: {},
    images: [],
    downloads: []
  };

  try {
    // Extract title
    const titleMatch = html.match(/<h1[^>]*>([^<]+)<\/h1>/i);
    if (titleMatch) data.name = cleanText(titleMatch[1]);

    // Extract SKU
    const skuMatch = html.match(/SKU[:\s]*([A-Z0-9-]+)/i);
    if (skuMatch) data.sku = skuMatch[1];

    // Extract price
    const priceMatch = html.match(/\$[\d,]+\.?\d*/);
    if (priceMatch) data.price = priceMatch[0];

    // Extract description
    const descMatch = html.match(/description[\s\S]{0,500}?<p>([\s\S]*?)<\/p>/i);
    if (descMatch) data.description = cleanText(descMatch[1]);

    // Extract product images
    const imgRegex = /https:\/\/www\.omc-stepperonline\.com\/image\/cache\/[^\s"'<>]+(?:-500x500|-250x250)[^\s"'<>]*/gi;
    const imgMatches = html.matchAll(imgRegex);
    for (const match of imgMatches) {
      const imgUrl = match[0];
      if (!imgUrl.includes('/23menu/') && !imgUrl.includes('logo-')) {
        if (!data.images.includes(imgUrl)) {
          data.images.push(imgUrl);
        }
      }
    }

    // Extract specifications
    const specRegex = /<td[^>]*>\s*([^<]+)\s*<\/td>\s*<td[^>]*>\s*([^<]+)\s*<\/td>/gi;
    const specMatches = html.matchAll(specRegex);
    for (const match of specMatches) {
      const key = cleanText(match[1]);
      const value = cleanText(match[2]);
      if (key && value && key.length < 100 && value.length < 500) {
        data.specifications[key] = value;
      }
    }

    // Extract downloads
    const dlRegex = /href="([^"]+\.(?:pdf|datasheet|manual|step|stp))"[^>]*>\s*([^<]+)/gi;
    const dlMatches = html.matchAll(dlRegex);
    for (const match of dlMatches) {
      data.downloads.push({
        name: cleanText(match[2]),
        url: match[1]
      });
    }
  } catch (e) {
    // Ignore parse errors
  }

  return data;
}

function cleanText(text) {
  return text.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
}
