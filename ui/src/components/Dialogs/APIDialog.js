import React, { Component } from 'react';
import PropTypes from 'prop-types';
import Dialog from './Dialog';
import cookie from 'react-cookies';
import renderValueElement from '../Common/renderValueElement';
import { API_ENDPOINT } from '../../configConsts';
import './APIDialog.css';


export default class APIDialog extends Component {
  static propTypes = {
    onClose: PropTypes.func.isRequired,
  }

  constructor(props) {
    super(props);
    let token = cookie.load('refresh_token');
    // TODO remove after demo
    if (token === 'Not assigned') {
      token = cookie.load('access_token');
    }

    this.state = {
      token: token,
    };
  }

  render() {
    const token = this.state.token;
    const code =
`#!/usr/bin/env python
from plynx.api import Operation, Graph, Client

TOKEN = '` + token + `'
ENDPOINT = '` + API_ENDPOINT + `'

Echo = Operation(
    id='5bb5a424fad58d56ffa84952',
    outputs=['output'],
    params=['text'],
)

echo = Echo(
    text='hello world',
)

graph = Graph(
    Client(
        token=TOKEN,
        endpoint=ENDPOINT,
    ),
    title='Hello World',
    description='Basic API example',
    targets=[echo]
)

graph.approve().wait()
`;

    return (
      <Dialog className='api-dialog'
              onClose={() => {
                this.props.onClose();
              }}
              width={900}
              height={700}
              title={'python API'}
              enableResizing={false}
      >
        <div className="api-dialog-content selectable">
          <div className='token-box'>
            <div className='token-label'>
              Your API token:
            </div>
            <textarea
              className='token'
              value={token}
              rows={2}
              readOnly
              />
          </div>
          <div className='token-box'>
            <div className='token-label'>
              Example:
            </div>
            {renderValueElement({
              parameterType: 'code',
              value: {
                mode: 'python',
                value: code,
              },
              handleChange: null,
              readOnly: true,
              height: '550px',
            })}
          </div>

        </div>

      </Dialog>
    );
  }
}
