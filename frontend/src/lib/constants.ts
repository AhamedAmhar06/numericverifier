export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || 'http://localhost:8877';

export const APPLE_EXAMPLE_QUESTION = "What was Apple revenue in FY2023?";

export const APPLE_EXAMPLE_EVIDENCE = {
  type: 'table',
  content: {
    title: 'Apple FY2023 Income Statement',
    columns: ['', 'FY2023', 'FY2022'],
    rows: [
      ['Net sales', '383,285', '394,328'],
      ['Cost of sales', '214,137', '223,546'],
      ['Gross margin', '169,148', '170,782'],
      ['Operating expenses', '54,847', '51,345'],
      ['Operating income', '114,301', '119,437'],
      ['Income taxes', '29,749', '19,300'],
      ['Net income', '96,995', '99,803'],
    ],
    units: {
      FY2023: 'millions USD',
      FY2022: 'millions USD',
    },
  },
};
