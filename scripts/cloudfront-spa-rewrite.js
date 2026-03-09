// CloudFront Function — Viewer Request
// Rewrites SPA routes to serve index.html from the correct directory.
// For unknown routes, S3 will return 403 → CloudFront Custom Error Response
// will serve /404.html (configure this in CloudFront distribution settings).
//
// Deploy:
//   1. CloudFront Console → Functions → Create function
//   2. Name: kureita-spa-rewrite
//   3. Paste this code → Publish
//   4. Go to Distribution → Behaviors → Default → Function associations
//   5. Set Viewer request → kureita-spa-rewrite
//
// Also configure Custom Error Responses on the distribution:
//   - HTTP Error Code: 403 → Response Page Path: /404.html → HTTP Response Code: 404
//   - HTTP Error Code: 404 → Response Page Path: /404.html → HTTP Response Code: 404

function handler(event) {
    var request = event.request;
    var uri = request.uri;

    // If the URI has a file extension (e.g., .js, .css, .png, .ico), serve as-is
    if (uri.match(/\.\w+$/)) {
        return request;
    }

    // If URI ends with /, append index.html
    if (uri.endsWith('/')) {
        request.uri = uri + 'index.html';
        return request;
    }

    // For paths without trailing slash (e.g., /login, /dashboard),
    // append /index.html
    request.uri = uri + '/index.html';

    return request;
}
