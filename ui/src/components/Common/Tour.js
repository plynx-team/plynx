import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import { TourProvider, useTour } from '@reactour/tour';

function TourController({ isOpen, steps }) {
  const { setIsOpen, setSteps, setCurrentStep } = useTour();

  useEffect(() => {
    const normalized = (steps || []).map((step) => ({
      ...step,
      selector: step.selector || 'body',
    }));
    setSteps(normalized);
    setCurrentStep(0);
    setIsOpen(Boolean(isOpen && normalized.length > 0));
  }, [isOpen, steps, setIsOpen, setSteps, setCurrentStep]);

  return null;
}

TourController.propTypes = {
  isOpen: PropTypes.bool,
  steps: PropTypes.array,
};

export default function Tour({ steps = [], isOpen = false, maskSpace = 10, rounded = 10, onRequestClose }) {
  if (!isOpen || !steps || steps.length === 0) {
    return null;
  }

  const normalizedSteps = steps.map((step) => ({
    ...step,
    selector: step.selector || 'body',
  }));

  return (
    <TourProvider
      steps={normalizedSteps}
      defaultOpen
      padding={{ mask: maskSpace, popover: [10, 10] }}
      beforeClose={() => {
        if (onRequestClose) {
          onRequestClose();
        }
      }}
      styles={{
        popover: (base) => ({
          ...base,
          backgroundColor: '#202020',
          color: '#ffffff',
          border: '1px solid #12ccc8',
          borderRadius: rounded,
        }),
        maskArea: (base) => ({
          ...base,
          rx: rounded,
        }),
        badge: (base) => ({
          ...base,
          backgroundColor: '#12ccc8',
          color: '#111',
        }),
        close: (base) => ({
          ...base,
          color: '#ffffff',
        }),
      }}
    >
      <TourController isOpen={isOpen} steps={steps} />
    </TourProvider>
  );
}

Tour.propTypes = {
  steps: PropTypes.array,
  isOpen: PropTypes.bool,
  maskSpace: PropTypes.number,
  rounded: PropTypes.number,
  onRequestClose: PropTypes.func,
};
