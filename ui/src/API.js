import { API_ENDPOINT } from './configConsts';
import { COLLECTIONS } from './constants';
import cookie from 'react-cookies';

const axios = require('axios');

class API {
  constructor({ url }) {
    this.url = url;
    this.endpoints = {};
  }

  /**
   * Create and store a single entity's endpoints
   * @param {A entity Object} entity
   */
  createEntity(entity) {
    this.endpoints[entity.name] = this.createBasicCRUDEndpoints(entity);
  }

  createEntities(arrayOfEntity) {
    arrayOfEntity.forEach(this.createEntity.bind(this));
  }

  /**
   * Create the basic endpoints handlers for CRUD operations
   * @param {A entity Object} entity
   */
  createBasicCRUDEndpoints({name}) {
    const endpoints = {};

    const resouceURL = `${this.url}/${name}`;

    endpoints.getAll = (query) => axios.get(resouceURL, { params: query, auth: { username: cookie.load('access_token') } });

    endpoints.getOne = ({ id }) => axios.get(`${resouceURL}/${id}`, { auth: { username: cookie.load('access_token') } });

    endpoints.getCustom = (body) => axios({url: resouceURL, ...body});

    endpoints.create = (toCreate) => axios.post(resouceURL, toCreate, { auth: { username: cookie.load('access_token') } });

    endpoints.upload = (toCreate, config) => axios.post(resouceURL, toCreate, { auth: { username: cookie.load('access_token') }, ...config});

    endpoints.update = (toUpdate) => axios.put(`${resouceURL}/${toUpdate.id}`, toUpdate, { auth: { username: cookie.load('access_token') } });

    endpoints.delete = ({ id }) => axios.delete(`${resouceURL}/${id}`, { auth: { username: cookie.load('access_token') } });

    return endpoints;
  }

  async getAccessToken() {
    let isSuccessfull = false;
    await this.endpoints.token.getCustom({
      method: 'get',
      auth:
      {
        username: cookie.load('refresh_token')
      }
    })
    .then(response => {
      cookie.save('access_token', response.data.access_token, { path: '/' });
      cookie.save('refresh_token', response.data.refresh_token, { path: '/' });
      cookie.save('user', response.data.user, { path: '/' });
      cookie.save('settings', response.data.settings, { path: '/' });
      console.log("Successfully updated token");
      isSuccessfull = true;
    })
    .catch(() => {
      console.log("Failed to update token");
      isSuccessfull = false;
    });
    return isSuccessfull;
  }
}

const plynxApi = new API({ url: API_ENDPOINT });
plynxApi.createEntity({ name: COLLECTIONS.TEMPLATES });
plynxApi.createEntity({ name: COLLECTIONS.RUNS });
plynxApi.createEntity({ name: COLLECTIONS.GROUPS });
plynxApi.createEntity({ name: COLLECTIONS.USERS });
plynxApi.createEntity({ name: 'resource' });
plynxApi.createEntity({ name: 'token' });
plynxApi.createEntity({ name: 'register' });
plynxApi.createEntity({ name: 'demo' });
plynxApi.createEntity({ name: 'user_settings' });
plynxApi.createEntity({ name: 'pull_settings' });
plynxApi.createEntity({ name: 'worker_states' });
plynxApi.createEntity({ name: `search_${COLLECTIONS.TEMPLATES}` });
plynxApi.createEntity({ name: `search_${COLLECTIONS.RUNS}` });
plynxApi.createEntity({ name: `search_${COLLECTIONS.GROUPS}` });
plynxApi.createEntity({ name: `search_in_hubs` });
plynxApi.createEntity({ name: `upload_file` });

export const PLynxApi = plynxApi;
