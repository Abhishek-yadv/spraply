import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import type * as Redocusaurus from 'redocusaurus';


const config: Config = {
  title: 'Spraply',
  tagline: 'Transform Web Content into LLM-Ready Data',
  favicon: 'img/favicon.ico',

  url: 'https://spraply.dev',
  baseUrl: '/',

  organizationName: 'Spraply',
  projectName: 'Spraply',

  onBrokenLinks: 'warn',
  onBrokenMarkdownLinks: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: '/',
          editUrl:
            'https://github.com/Spraply/docs/tree/main/',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
    [
      'redocusaurus',
      {
        // Plugin Options for loading OpenAPI files
        specs: [
          // Pass it a path to a local OpenAPI YAML file
          // {
          //   // Redocusaurus will automatically bundle your spec into a single file during the build
          //   spec: 'openapi/api.yaml',
          //   route: '/api-test/',
          // },
          // You can also pass it a OpenAPI spec URL
          {
            spec: 'https://app.spraply.dev/api/schema/team',
            route: '/api/documentation/',
          },
        ],
        // Theme Options for modifying how redoc renders them
        theme: {
          // Change with your site colors
          primaryColor: '#1890ff',
        },
      },
    ] satisfies Redocusaurus.PresetEntry,

  ],


  themeConfig: {
    // Replace with your project's social card
    image: 'img/Spraply-social-card.jpg',
    navbar: {
      title: 'Spraply',
      logo: {
        alt: 'Spraply Logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Documentation',
        },
        {
          type: 'docSidebar',
          sidebarId: 'clientSidebar',
          position: 'left',
          label: 'Clients',
        },
        {
          to: '/api/documentation/',
          label: 'API Reference',
          position: 'left',
        },
        {
          href: 'https://github.com/Abhishek-yadv/Spraply',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Community',
          items: [
            {
              label: 'Discord',
              href: 'https://discord.gg/8bwgBWeXYr',
            },
            {
              label: 'GitHub',
              href: 'https://github.com/Abhishek-yadv/Spraply',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'Self-Hosted',
              href: 'https://github.com/Spraply/self-hosted#readme',
            },
          ],
        },
      ],
      copyright: `Copyright ${new Date().getFullYear()} Spraply. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
