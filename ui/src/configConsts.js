let backendHost;
const apiVersion = 'v0';

const hostname = window && window.location && window.location.hostname;

if (hostname === 'plynx.com') {
  backendHost = 'https://plynx.com';
} else if (hostname === 'localhost') {
  backendHost = process.env.REACT_APP_BACKEND_HOST || 'http://localhost:5005';
} else {
  backendHost = '';
}
backendHost = "http://192.168.1.3:5005"

export const API_ENDPOINT = `${backendHost}/plynx/api/${apiVersion}`;
