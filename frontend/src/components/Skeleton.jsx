import React from 'react';

export function Skeleton({ className }) {
  return (
    <div
      className={`skeleton ${className}`}
    />
  );
}

export function ProfileSkeleton() {
  return (
    <div style={{ display: 'grid', gap: '24px' }}>
      {/* Profile Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <Skeleton style={{ height: '96px', width: '96px', borderRadius: '9999px' }} />
        <div style={{ display: 'grid', gap: '8px', flex: 1 }}>
          <Skeleton style={{ height: '24px', width: '75%' }} />
          <Skeleton style={{ height: '16px', width: '50%' }} />
        </div>
      </div>

      {/* Form inputs */}
      <div style={{ display: 'grid', gap: '16px' }}>
        <Skeleton style={{ height: '40px', width: '100%' }} />
        <Skeleton style={{ height: '40px', width: '100%' }} />
      </div>

      {/* CV List */}
      <div style={{ display: 'grid', gap: '16px' }}>
        <Skeleton style={{ height: '24px', width: '25%' }} />
        <div style={{ display: 'grid', gap: '12px' }}>
          <Skeleton style={{ height: '64px', width: '100%' }} />
          <Skeleton style={{ height: '64px', width: '100%' }} />
          <Skeleton style={{ height: '64px', width: '100%' }} />
        </div>
      </div>
    </div>
  );
}

export function GenerateSkeleton() {
  return (
    <div style={{ margin: '24px auto', maxWidth: 1080 }}>
      <Skeleton style={{ height: '36px', width: '40%', marginBottom: '12px' }} />
      <div className="grid-2" style={{ marginTop: 12, alignItems: 'start' }}>
        {/* Left Column: Form */}
        <div className="card">
          <div className="card-body stack">
            <Skeleton style={{ height: '20px', width: '30%' }} />
            <Skeleton style={{ height: '240px', width: '100%' }} />
            <Skeleton style={{ height: '40px', width: '100%' }} />
          </div>
        </div>
        {/* Right Column: Options */}
        <div className="stack">
          <div className="card">
            <div className="card-body stack">
              <Skeleton style={{ height: '20px', width: '40%' }} />
              <Skeleton style={{ height: '64px', width: '100%' }} />
              <Skeleton style={{ height: '64px', width: '100%' }} />
              <Skeleton style={{ height: '64px', width: '100%' }} />
              <Skeleton style={{ height: '20px', width: '25%', marginTop: '16px' }} />
              <Skeleton style={{ height: '40px', width: '100%' }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function DocumentsSkeleton() {
  const renderList = () => (
    <div className="stack">
      <Skeleton style={{ height: '72px', width: '100%' }} />
      <Skeleton style={{ height: '72px', width: '100%' }} />
      <Skeleton style={{ height: '72px', width: '100%' }} />
    </div>
  );

  return (
    <div>
      <Skeleton style={{ height: '36px', width: '30%', marginTop: 0, marginBottom: 8 }} />
      
      <section style={{ marginTop: 8 }}>
        <Skeleton style={{ height: '28px', width: '15%', marginTop: 0, marginBottom: 16 }} />
        {renderList()}
      </section>

      <section style={{ marginTop: 24 }}>
        <Skeleton style={{ height: '28px', width: '25%', marginTop: 0, marginBottom: 16 }} />
        {renderList()}
      </section>
    </div>
  );
}
