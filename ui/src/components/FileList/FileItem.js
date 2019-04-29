import React, { Component } from 'react';
import PropTypes from 'prop-types';
import {listTextElement} from '../Common/listElements';
import {ResourceConsumer} from '../../contexts';
import Icon from '../Common/Icon';
import {NODE_STATUS} from '../../constants';
import './FileItem.css';

export default class FileItem extends Component {
  static propTypes = {
    _id: PropTypes.string,
    title: PropTypes.string,
    description: PropTypes.string,
    starred: PropTypes.bool,
    node_status: PropTypes.oneOf(Object.values(NODE_STATUS)),
    user: PropTypes.shape({
      username: PropTypes.string,
    }),
    insertion_date: PropTypes.string,
    file_type: PropTypes.string,
    fileObj: PropTypes.object,
    onClick: PropTypes.func,
  };

  onClick(e) {
    e.stopPropagation();
    e.preventDefault();
    this.props.onClick(this.props.fileObj);
  }

  render() {
    return (
      <a className='list-item file-list-item' href={null} onClick={(e) => this.onClick(e)}>

        <div className='ItemHeader'>
          <div className='TitleDescription'>
            <div className='Title'>
              {this.props.title}
            </div>
            <div className='Description'>
              &ldquo;{this.props.description}&rdquo;
            </div>
          </div>
          <div className={this.props.starred ? 'star-visible' : 'star-hidden'}>
            <img src="/icons/star.svg" alt="star" />
          </div>
        </div>

        <div className={'Type'}>
          <ResourceConsumer className={'Type'}>
          { resources_dict => <div className='Widget'>
              <Icon
                type_descriptor={resources_dict[this.props.file_type]}
                width={"20"}
                height={"20"}
              />

              {resources_dict[this.props.file_type].alias}
            </div>
          }
          </ResourceConsumer>
        </div>
        { listTextElement('Status ' + this.props.node_status, this.props.node_status) }
        { listTextElement('Id', this.props._id) }
        { listTextElement('Author', this.props.user.username) }
        { listTextElement('Created', this.props.insertion_date) }
      </a>
    );
  }
}
