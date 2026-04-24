{
  description = "Canvas Scraper devEnv";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pythonEnv = pkgs.python3.withPackages (
          ps: with ps; [
            requests
            python-dotenv
            # playwright
          ]
        );
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            # pkgs.playwright-driver.browsers
          ];

          shellHook = ''
            # export PLAYWRIGHT_BROWSERS_PATH=${pkgs.playwright-driver.browsers}
            # export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
            echo "Canvas Scraper environment loaded!"
            echo "Ensure your .env file is populated with CANVAS_API_TOKEN"
          '';
        };
      }
    );
}
