{
  description = "Development checks for prune-runner";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs =
    { self, nixpkgs }:
    let
      forSystems = nixpkgs.lib.genAttrs [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      tools = pkgs: [
        pkgs.python3
        pkgs.ruff
        pkgs.actionlint
        pkgs.nixfmt
      ];
    in
    {
      checks = forSystems (system: {
        default =
          let
            pkgs = nixpkgs.legacyPackages.${system};
          in
          pkgs.runCommand "prune-runner-check" { nativeBuildInputs = tools pkgs; } ''
            cp -R ${self} source
            chmod -R u+w source
            cd source
            ./check.sh
            touch $out
          '';
      });
      packages = forSystems (system: {
        default = self.checks.${system}.default;
      });
      devShells = forSystems (system: {
        default = nixpkgs.legacyPackages.${system}.mkShell {
          packages = tools nixpkgs.legacyPackages.${system};
        };
      });
    };
}
