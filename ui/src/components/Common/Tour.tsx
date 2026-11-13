import React, { useEffect } from 'react';
// @ts-ignore
import { TourProvider, useTour } from '@reactour/tour';

export interface TourProps {
  steps?: any[];
  isOpen?: boolean;
  maskSpace?: number;
  rounded?: number;
  onRequestClose?: () => void;
}

function TourController({ isOpen, steps }: { isOpen?: boolean; steps?: any[] }) {
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

export default function Tour({
  steps = [],
  isOpen = false,
  maskSpace = 10,
  rounded = 10,
  onRequestClose,
}: TourProps) {
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
        popover: (base: any) => ({
          ...base,
          backgroundColor: '#202020',
          color: '#ffffff',
          border: '1px solid #12ccc8',
          borderRadius: rounded,
        }),
        maskArea: (base: any) => ({
          ...base,
          rx: rounded,
        }),
        badge: (base: any) => ({
          ...base,
          backgroundColor: '#12ccc8',
          color: '#111',
        }),
        close: (base: any) => ({
          ...base,
          color: '#ffffff',
        }),
      }}
    >
      <TourController isOpen={isOpen} steps={steps} />
    </TourProvider>
  );
}
