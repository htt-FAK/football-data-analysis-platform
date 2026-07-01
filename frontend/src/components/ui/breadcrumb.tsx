import { Link } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";

interface BreadcrumbItem {
  label: string;
  to?: string;
}

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className="flex items-center gap-1.5 mb-4 text-xs text-muted-foreground">
      <Link to="/" className="hover:text-primary transition-colors">
        <Home className="w-3.5 h-3.5" />
      </Link>
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <ChevronRight className="w-3 h-3 text-muted-foreground/50" />
          {item.to && i < items.length - 1 ? (
            <Link to={item.to} className="hover:text-primary transition-colors font-medium">
              {item.label}
            </Link>
          ) : (
            <span className="text-foreground font-semibold">{item.label}</span>
          )}
        </div>
      ))}
    </nav>
  );
}
