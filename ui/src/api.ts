import axios, { AxiosPromise, AxiosRequestConfig } from 'axios';
import { API_ENDPOINT } from './config';
import { COLLECTIONS } from './constants';
import cookie from './cookie';

export interface EndpointHandlers {
  getAll: (query?: any) => AxiosPromise<any>;
  getOne: (params: { id: string }) => AxiosPromise<any>;
  getCustom: (config: AxiosRequestConfig) => AxiosPromise<any>;
  create: (toCreate: any) => AxiosPromise<any>;
  upload: (toCreate: any, config?: AxiosRequestConfig) => AxiosPromise<any>;
  update: (toUpdate: { id: string; [key: string]: any }) => AxiosPromise<any>;
  delete: (params: { id: string }) => AxiosPromise<any>;
}

class API {
  url: string;
  endpoints: Record<string, EndpointHandlers>;

  constructor({ url }: { url: string }) {
    this.url = url;
    this.endpoints = {};
  }

  createEntity(entity: { name: string }): void {
    this.endpoints[entity.name] = this.createBasicCRUDEndpoints(entity);
  }

  createEntities(arrayOfEntity: { name: string }[]): void {
    arrayOfEntity.forEach(this.createEntity.bind(this));
  }

  createBasicCRUDEndpoints({ name }: { name: string }): EndpointHandlers {
    const resourceURL = `${this.url}/${name}`;

    return {
      getAll: (query?: any) =>
        axios.get(resourceURL, {
          params: query,
          auth: { username: cookie.load('access_token'), password: '' },
        }),

      getOne: ({ id }: { id: string }) =>
        axios.get(`${resourceURL}/${id}`, {
          auth: { username: cookie.load('access_token'), password: '' },
        }),

      getCustom: (config: AxiosRequestConfig) =>
        axios({ url: resourceURL, ...config }),

      create: (toCreate: any) =>
        axios.post(resourceURL, toCreate, {
          auth: { username: cookie.load('access_token'), password: '' },
        }),

      upload: (toCreate: any, config?: AxiosRequestConfig) =>
        axios.post(resourceURL, toCreate, {
          auth: { username: cookie.load('access_token'), password: '' },
          ...config,
        }),

      update: (toUpdate: { id: string; [key: string]: any }) =>
        axios.put(`${resourceURL}/${toUpdate.id}`, toUpdate, {
          auth: { username: cookie.load('access_token'), password: '' },
        }),

      delete: ({ id }: { id: string }) =>
        axios.delete(`${resourceURL}/${id}`, {
          auth: { username: cookie.load('access_token'), password: '' },
        }),
    };
  }

  async getAccessToken(): Promise<boolean> {
    let isSuccessfull = false;
    await this.endpoints.token
      .getCustom({
        method: 'get',
        auth: {
          username: cookie.load('refresh_token'),
          password: '',
        },
      })
      .then((response) => {
        cookie.save('access_token', response.data.access_token, { path: '/' });
        cookie.save('refresh_token', response.data.refresh_token, { path: '/' });
        cookie.save('user', response.data.user, { path: '/' });
        cookie.save('settings', response.data.settings, { path: '/' });
        console.log('Successfully updated token');
        isSuccessfull = true;
      })
      .catch(() => {
        console.log('Failed to update token');
        isSuccessfull = false;
      });
    return isSuccessfull;
  }
}

const plynxApi = new API({ url: API_ENDPOINT });
plynxApi.createEntity({ name: COLLECTIONS.TEMPLATES });
plynxApi.createEntity({ name: COLLECTIONS.RUNS });
plynxApi.createEntity({ name: COLLECTIONS.USERS });
plynxApi.createEntity({ name: 'resource' });
plynxApi.createEntity({ name: 'token' });
plynxApi.createEntity({ name: 'register' });
plynxApi.createEntity({ name: 'register_with_oauth2' });
plynxApi.createEntity({ name: 'user_settings' });
plynxApi.createEntity({ name: 'pull_settings' });
plynxApi.createEntity({ name: 'worker_states' });
plynxApi.createEntity({ name: `search_${COLLECTIONS.TEMPLATES}` });
plynxApi.createEntity({ name: `search_${COLLECTIONS.RUNS}` });
plynxApi.createEntity({ name: `search_in_hubs` });
plynxApi.createEntity({ name: `upload_file` });

export const PLynxApi = plynxApi;
export default PLynxApi;
