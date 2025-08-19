import React from 'react'
import { motion } from 'framer-motion'

const templates = [
  {
    id: 'classic',
    title: 'Classic',
    desc: 'Balanced, clean typographic layout',
    preview: (
      <div style={{ 
        width: '100%', 
        height: 120, 
        background: 'linear-gradient(180deg, #f8fafc, #f1f5f9)',
        border: '1px solid #e2e8f0',
        borderRadius: 8,
        padding: 12,
        fontSize: 8,
        color: '#334155',
        fontFamily: 'serif'
      }}>
        <div style={{ fontWeight: 'bold', marginBottom: 4, fontSize: 10 }}>John Doe</div>
        <div style={{ marginBottom: 6, fontSize: 7 }}>Software Engineer</div>
        <div style={{ height: 1, background: '#cbd5e1', marginBottom: 6 }}></div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 'bold', fontSize: 7, marginBottom: 2 }}>EXPERIENCE</div>
            <div style={{ fontSize: 6, lineHeight: 1.2 }}>Senior Developer<br/>Tech Corp • 2020-2023</div>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 'bold', fontSize: 7, marginBottom: 2 }}>SKILLS</div>
            <div style={{ fontSize: 6, lineHeight: 1.2 }}>React, Node.js<br/>Python, AWS</div>
          </div>
        </div>
      </div>
    ),
    colors: ['#1e293b', '#475569', '#64748b']
  },
  {
    id: 'modern',
    title: 'Modern',
    desc: 'Bold headings with accent color',
    preview: (
      <div style={{ 
        width: '100%', 
        height: 120, 
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        borderRadius: 8,
        padding: 12,
        fontSize: 8,
        color: 'white',
        fontFamily: 'sans-serif'
      }}>
        <div style={{ fontWeight: 'bold', marginBottom: 4, fontSize: 12, color: '#fbbf24' }}>JOHN DOE</div>
        <div style={{ marginBottom: 8, fontSize: 8, opacity: 0.9 }}>SOFTWARE ENGINEER</div>
        <div style={{ background: 'rgba(255,255,255,0.2)', height: 1, marginBottom: 6 }}></div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          <div>
            <div style={{ fontWeight: 'bold', fontSize: 7, marginBottom: 2, color: '#fbbf24' }}>EXPERIENCE</div>
            <div style={{ fontSize: 6, lineHeight: 1.2, opacity: 0.9 }}>Senior Dev<br/>Tech Corp</div>
          </div>
          <div>
            <div style={{ fontWeight: 'bold', fontSize: 7, marginBottom: 2, color: '#fbbf24' }}>SKILLS</div>
            <div style={{ fontSize: 6, lineHeight: 1.2, opacity: 0.9 }}>React<br/>Python</div>
          </div>
        </div>
      </div>
    ),
    colors: ['#667eea', '#764ba2', '#fbbf24']
  },
  {
    id: 'compact',
    title: 'Compact',
    desc: 'Space-efficient, concise structure',
    preview: (
      <div style={{ 
        width: '100%', 
        height: 120, 
        background: '#ffffff',
        border: '2px solid #059669',
        borderRadius: 4,
        padding: 8,
        fontSize: 7,
        color: '#111827',
        fontFamily: 'monospace'
      }}>
        <div style={{ 
          background: '#059669', 
          color: 'white', 
          padding: '2px 6px', 
          marginBottom: 4,
          fontSize: 8,
          fontWeight: 'bold'
        }}>
          JOHN DOE | SOFTWARE ENG
        </div>
        <div style={{ display: 'flex', gap: 4, fontSize: 6 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 'bold', marginBottom: 1 }}>EXP:</div>
            <div style={{ lineHeight: 1.1 }}>Sr Dev @ Tech<br/>2020-2023</div>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 'bold', marginBottom: 1 }}>TECH:</div>
            <div style={{ lineHeight: 1.1 }}>React, Node<br/>Python, AWS</div>
          </div>
        </div>
        <div style={{ marginTop: 4, fontSize: 6, color: '#059669' }}>
          john@email.com | +1234567890
        </div>
      </div>
    ),
    colors: ['#059669', '#10b981', '#34d399']
  }
]

export default function TemplateSelector({ selectedTemplate, onTemplateSelect }) {
  return (
    <div>
      <div className="label" style={{ marginBottom: 12 }}>Choose Template</div>
      <div style={{ display: 'grid', gap: 16 }}>
        {templates.map((template, index) => (
          <motion.div
            key={template.id}
            className="card"
            onClick={() => onTemplateSelect(template.id)}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            style={{
              cursor: 'pointer',
              borderWidth: selectedTemplate === template.id ? 2 : 1,
              borderColor: selectedTemplate === template.id ? 'var(--primary)' : 'var(--border)',
              background: selectedTemplate === template.id 
                ? 'linear-gradient(180deg, rgba(110, 168, 254, 0.1), rgba(59, 130, 246, 0.05))'
                : 'var(--card-bg)',
              transition: 'all 0.2s ease'
            }}
            aria-pressed={selectedTemplate === template.id}
          >
            <div className="card-body" style={{ padding: 16 }}>
              <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
                {/* Template Preview */}
                <div style={{ 
                  width: 140, 
                  flexShrink: 0,
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  overflow: 'hidden',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
                }}>
                  {template.preview}
                </div>
                
                {/* Template Info */}
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <h4 style={{ 
                      margin: 0, 
                      fontSize: 16, 
                      fontWeight: 600,
                      color: selectedTemplate === template.id ? 'var(--primary)' : 'var(--text)'
                    }}>
                      {template.title}
                    </h4>
                    {selectedTemplate === template.id && (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        style={{
                          width: 20,
                          height: 20,
                          borderRadius: '50%',
                          background: 'var(--primary)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'white',
                          fontSize: 12
                        }}
                      >
                        ✓
                      </motion.div>
                    )}
                  </div>
                  
                  <p style={{ 
                    margin: '0 0 12px 0', 
                    fontSize: 14, 
                    color: 'var(--muted)',
                    lineHeight: 1.4
                  }}>
                    {template.desc}
                  </p>
                  
                  {/* Color Palette */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 12, color: 'var(--muted)' }}>Colors:</span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {template.colors.map((color, i) => (
                        <div
                          key={i}
                          style={{
                            width: 16,
                            height: 16,
                            borderRadius: '50%',
                            background: color,
                            border: '1px solid var(--border)'
                          }}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
