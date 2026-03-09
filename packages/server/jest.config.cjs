module.exports = {
  testEnvironment: 'node',
  roots: ['<rootDir>/src'],
  testMatch: ['**/*.test.ts'],
  setupFiles: ['<rootDir>/src/test/setup-env.ts'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  transform: {
    '^.+\\.tsx?$': [
      'ts-jest',
      {
      tsconfig: {
        module: 'commonjs',
        esModuleInterop: true,
        baseUrl: '.',
        types: ['node', 'jest'],
        paths: {
          '@/*': ['src/*'],
        },
      },
      },
    ],
  },
};
