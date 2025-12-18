# An example that demonstrates how to clone and then customize an existing lens.
# usage:
#   python -m examples.lens_clone --api_key=<YOUR_API_KEY> --lens_id=<EXISTING_LENS_ID_TO_CLONE_FROM>
import logging

from archetypeai import ArchetypeAI, ArgParser, pformat


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Get the info about the existing lens we will clone from.
    origin_lens_metadata = client.lens.get_metadata(lens_id=args.lens_id)
    logging.info(pformat(prefix=f"Origin Lens:\n", data=origin_lens_metadata))

    # Clone an existing lens to create a unique copy of that lens.
    new_lens_metadata = client.lens.clone(args.lens_id)
    new_lens_id = new_lens_metadata["lens_id"]
    logging.info(pformat(prefix=f"New Lens:\n", data=new_lens_metadata))

    # Customize the lens arguments.
    if args.lens_name:
        new_lens_metadata["lens_name"] = args.lens_name
    if args.instruction:
        new_lens_metadata["lens_config"]["model_parameters"]["instruction"] = args.instruction
    if args.focus:
        new_lens_metadata["lens_config"]["model_parameters"]["focus"] = args.focus

    # Push the modified lens metadata back to the Archetype Platform.
    lens_metadata = client.lens.modify(new_lens_id, new_lens_metadata)
    logging.info(pformat(prefix=f"Customized Lens:\n", data=lens_metadata))


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--lens_id", required=True, type=str)
    parser.add_argument("--lens_name", default="", type=str)
    parser.add_argument("--instruction", default="", type=str)
    parser.add_argument("--focus", default="", type=str)
    args = parser.parse_args(configure_logging=True)
    main(args)