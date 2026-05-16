function ArchitectureCard({
  icon: Icon,
  title,
  description,
  variant = 'neutral',
  simple = false,
  highlight = false,
}) {
  const className = [
    simple ? 'architecture-card-simple' : 'architecture-card',
    `architecture-${variant}`,
    highlight ? 'architecture-highlight' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={className}>
      <h4>
        {Icon ? <Icon aria-hidden="true" /> : null}
        {title}
      </h4>
      {description ? <p>{description}</p> : null}
    </div>
  );
}

export default ArchitectureCard;
