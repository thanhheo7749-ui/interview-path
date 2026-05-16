const toneClassName = {
  blue: '',
  purple: 'tag-purple',
  green: 'tag-green',
  dark: 'tag-dark',
};

function Tag({ children, tone = 'blue' }) {
  return <span className={`tag ${toneClassName[tone] || ''}`.trim()}>{children}</span>;
}

export default Tag;
