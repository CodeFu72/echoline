/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./app/**/*.py", "./static/js/**/*.js"],
  safelist: [
    // Keep arbitrary z-index utilities from being purged
    'z-[9998]',
    'z-[9999]',
  ],
  theme: {
    extend: {
      // Named z-indexes (optional, lets you use `z-modal` / `z-overlay`)
      zIndex: {
        overlay: 9998,
        modal: 10000,
      },

      maxWidth: { measure: "68ch" },
      typography: ({ theme }) => ({
        invert: {
          css: {
            "--tw-prose-body": theme("colors.neutral.200"),
            "--tw-prose-headings": "#fff",
            "--tw-prose-links": theme("colors.teal.300"),
            "--tw-prose-bold": "#fff",
            "--tw-prose-counters": theme("colors.neutral.400"),
            "--tw-prose-bullets": theme("colors.neutral.600"),
            "--tw-prose-hr": theme("colors.neutral.800"),
            "--tw-prose-quotes": theme("colors.neutral.100"),
            "--tw-prose-quote-borders": theme("colors.teal.700"),
            "--tw-prose-captions": theme("colors.neutral.400"),
            "--tw-prose-code": theme("colors.neutral.100"),
            "--tw-prose-pre-code": theme("colors.neutral.100"),
            "--tw-prose-pre-bg": theme("colors.neutral.900"),
            "--tw-prose-th-borders": theme("colors.neutral.800"),
            "--tw-prose-td-borders": theme("colors.neutral.800"),
            h1: { marginTop: "0", letterSpacing: "-0.01em" },
            h2: { letterSpacing: "-0.01em" },
            a: { textDecoration: "none" },
            "a:hover": { textDecoration: "underline" },
            blockquote: {
              fontStyle: "normal",
              borderLeftColor: theme("colors.teal.700"),
              borderLeftWidth: "3px",
              paddingLeft: "1rem",
              color: theme("colors.neutral.100"),
            },
            img: { borderRadius: theme("borderRadius.xl") },
            "figure figcaption": {
              color: theme("colors.neutral.400"),
              textAlign: "center",
              marginTop: ".5rem",
            },
            code: { fontWeight: "500" },
            pre: { borderRadius: theme("borderRadius.xl") },
          },
        },

        /* 👇 custom long-form reading style */
        reader: {
          css: {
            maxWidth: "68ch",
            lineHeight: "1.9",
            fontSize: "18px",
            "p, ul, ol, blockquote, pre, table": {
              marginTop: "1.15em",
              marginBottom: "1.15em",
            },
            h1: {
              fontWeight: "800",
              letterSpacing: "-0.02em",
              marginBottom: "0.8em",
            },
            h2: { fontWeight: "700", letterSpacing: "-0.01em" },
            "ul > li, ol > li": { paddingLeft: "0.15em" },
            "ul > li::marker": { color: theme("colors.neutral.500") },
            "ol > li::marker": { color: theme("colors.neutral.500") },
            blockquote: {
              borderLeftWidth: "3px",
              borderLeftColor: theme("colors.teal.700"),
              paddingLeft: "1rem",
            },
            strong: { color: "#fff" },
            img: { borderRadius: theme("borderRadius.xl") },
            hr: { borderColor: theme("colors.neutral.800") },
          },
        },
      }),
    },
  },
  plugins: [require("@tailwindcss/typography")],
};