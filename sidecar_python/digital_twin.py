class DigitalTwin:

    @staticmethod
    def display(ship, num_bays=None):
        """
        Render a console cross-section of the ship.
        num_bays defaults to the highest bay number found on any container,
        so it works even when Ship has no num_bays attribute.
        """

        if num_bays is None:
            if ship.containers:
                num_bays = max(c.bay for c in ship.containers)
            else:
                num_bays = 10          # sensible fallback for an empty ship

        print("\n===== DIGITAL TWIN =====\n")

        for bay in range(1, num_bays + 1):

            port = ""
            center = ""
            starboard = ""

            for c in ship.containers:

                if c.bay == bay:

                    if c.side == "port":
                        port += f"[{c.id}:{c.weight}t]"

                    elif c.side == "center":
                        center += f"[{c.id}:{c.weight}t]"

                    elif c.side == "starboard":
                        starboard += f"[{c.id}:{c.weight}t]"

            print(
                f"Bay {bay:02d} | "
                f"P:{port:<18} "
                f"C:{center:<18} "
                f"S:{starboard:<18}"
            )
