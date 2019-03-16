import React, { Component } from 'react';
import { listTextElement } from '../Common/listElements';
import { FILE_TYPES } from '../../constants.js'
import './FileItem.css';

export default class FileItem extends Component {
  onClick(e) {
    e.stopPropagation();
    e.preventDefault();
    this.props.onClick(this.props.fileObj);
  }

  render() {
    var typeTuple = FILE_TYPES.filter(
      (ft) => {return ft.type === this.props.file_type}
    )[0];

    return (
      <a className='list-item file-list-item' href={null} onClick={(e)=>this.onClick(e)}>
        <div className='TitleDescription'>
          <div className='Title'>
            {this.props.title}
          </div>
          <div className='Description'>
            &ldquo;{this.props.description}&rdquo;
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
