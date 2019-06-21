import React from 'react';


export default function makePropertiesBox(title, content) {
  return <div className="PropertiesBox">
            <div className="PropertiesBoxHeader">
              { title }
            </div>
            <div className="PropertiesBoxContent">
              { content }
            </div>
          </div>;
}
