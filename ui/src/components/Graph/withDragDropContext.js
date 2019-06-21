import {DragDropContext} from 'react-dnd';
import { isMobile } from "react-device-detect";
import TouchBackend from 'react-dnd-touch-backend';
import HTML5Backend from 'react-dnd-html5-backend';

export default DragDropContext(isMobile ? TouchBackend : HTML5Backend);
