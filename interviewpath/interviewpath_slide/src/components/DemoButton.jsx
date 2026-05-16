import { LoaderCircle, Sparkles } from 'lucide-react';

function DemoButton({
  children,
  className = '',
  loading = false,
  icon: Icon = Sparkles,
  type = 'button',
  ...buttonProps
}) {
  return (
    <button className={`ai-btn ${className}`.trim()} type={type} {...buttonProps}>
      {loading ? (
        <LoaderCircle className="button-icon spinning" aria-hidden="true" />
      ) : (
        <Icon className="button-icon" aria-hidden="true" />
      )}
      {children}
    </button>
  );
}

export default DemoButton;
