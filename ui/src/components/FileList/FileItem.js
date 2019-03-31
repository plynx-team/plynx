import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { listTextElement } from '../Common/listElements';
import { FILE_TYPES, NODE_STATUS } from '../../constants';
import './FileItem.css';

export default class FileItem extends Component {
  onClick(e) {
    e.stopPropagation();
    e.preventDefault();
    this.props.onClick(this.props.fileObj);
  }

  render() {
    const typeTuple = FILE_TYPES.filter(
      (ft) => {
        return ft.type === this.props.file_type;
      }
    )[0];

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
          <div className='Widget'>
            <img src={"/icons/file_types/" + this.props.file_type + ".svg"} width="20" height="20" alt={this.props.file_type}/>
            {typeTuple.alias}
          </div>
        </div>
        { listTextElement('Status ' + this.props.node_status, this.props.node_status) }
        { listTextElement('Id', this.props._id) }
        { listTextElement('Author', this.props.user.username) }
        { listTextElement('Created', this.props.insertion_date) }
      </a>
    );
  }
}

FileItem.propTypes = {
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
