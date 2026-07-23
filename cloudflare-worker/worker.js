// Cloudflare Worker — Job Portal Update Trigger
// Deploy করুন: https://workers.cloudflare.com
// Secret add করুন: GITHUB_TOKEN (repo + workflow scope)

export default {
  async fetch(request, env) {
    const headers = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Content-Type': 'application/json'
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers });
    }

    if (request.method !== 'POST') {
      return new Response(JSON.stringify({ error: 'POST only' }), { status: 405, headers });
    }

    try {
      const r = await fetch(
        'https://api.github.com/repos/EkramulKU/jobportal/actions/workflows/update_circulars.yml/dispatches',
        {
          method: 'POST',
          headers: {
            'Authorization': `token ${env.GITHUB_TOKEN}`,
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'User-Agent': 'JobPortalWorker/1.0'
          },
          body: JSON.stringify({ ref: 'master' })
        }
      );

      if (r.status === 204) {
        return new Response(JSON.stringify({ ok: true, message: 'Update triggered!' }), { headers });
      } else {
        const text = await r.text();
        return new Response(JSON.stringify({ ok: false, status: r.status, detail: text }), { status: r.status, headers });
      }
    } catch (err) {
      return new Response(JSON.stringify({ ok: false, error: err.message }), { status: 500, headers });
    }
  }
};
