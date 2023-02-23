let backendHost;
const apiVersion = 'v0';

const hostname = window && window.location && window.location.hostname;

console.log("Host:", hostname);
// `hostname` equals to platform.plynx.com, test.plynx.com etc
if (hostname === 'plynx.com' || hostname === 'platform.plynx.com' || hostname === 'test.plynx.com') {
  backendHost = 'https://api.plynx.com';
} else if (hostname === 'localhost') {
  backendHost = process.env.REACT_APP_BACKEND_HOST || 'http://localhost:5005';
} else {
  backendHost = '';
}

export const API_ENDPOINT = `${backendHost}/plynx/api/${apiVersion}`;
