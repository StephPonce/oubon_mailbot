import React from 'react';

interface PageWrapperProps {
  children: React.ReactNode;
  maxWidth?: 'full' | '7xl' | '6xl';
}

export const PageWrapper: React.FC<PageWrapperProps> = ({ children, maxWidth = '7xl' }) => {
  const maxWidthClass = maxWidth === 'full' ? '' : `max-w-${maxWidth} mx-auto`;

  return (
    <div className="min-h-screen   p-12" style={{ perspective: '1500px' }}>
      <div className={`${maxWidthClass} space-y-8`}>
        {children}
      </div>
    </div>
  );
};
