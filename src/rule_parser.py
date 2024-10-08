import json
import logging
import os
from validator.file_validator import FileValidator
from validator.azd_validator import AzdValidator

# from validator.msdo_validator import MsdoValidator
from validator.topic_validator import TopicValidator
from validator.folder_validator import FolderValidator
from validator.azd_command import AzdCommand
import utils


class RuleParser:
    def __init__(self, rules_file_path, args):
        self.rules_file_path = rules_file_path
        self.args = args

    def parse(self):
        with open(self.rules_file_path, "r") as file:
            rules = json.load(file)
        
        validate_files = self.args.validate_paths.split(",") if self.args.validate_paths else []
        custom_rules = [os.path.splitext(file)[0].strip() for file in validate_files]
        for full_filename in validate_files:
            filename, ext = os.path.splitext(full_filename)
            filename = filename.strip()
            if rules.get(filename):
                rules[filename]["ext"] = self.normalize_extensions(ext)
                rules[filename]["assert_in"] = os.getenv(f"{filename.upper().replace('.', '_')}_H2_TAG", "").split(",")
            else:
                rules[filename] = {
                    "validator": "FileValidator",
                    "catalog": "source_code_structure",
                    "ext": self.normalize_extensions(ext),
                }
        logging.info(f"Validate paths: {custom_rules}")
        logging.info(f"Rules: {rules}")

        validators = []

        for rule_name, rule_details in rules.items():
            validator_type = rule_details.get("validator")
            catalog = rule_details.get("catalog", "")
            error_as_warning = rule_details.get("error_as_warning", False)

            if validator_type == "FileValidator":
                if custom_rules == "" or (custom_rules and rule_name not in custom_rules):
                    continue
                    
                ext = rule_details.get("ext", [])
                candidate_path = rule_details.get("candidate_path", ["."])
                case_sensitive = rule_details.get("case_sensitive", False)
                h2_tags = rule_details.get("assert_in", None)
                accept_folder = rule_details.get("accept_folder", False)

                validator = FileValidator(
                    catalog,
                    rule_name,
                    ext,
                    ".",
                    candidate_path,
                    h2_tags,
                    case_sensitive,
                    error_as_warning,
                    accept_folder,
                )
                validators.append(validator)

            elif validator_type == "FolderValidator":
                if custom_rules == "" or (custom_rules and rule_name not in custom_rules):
                    continue
                    
                candidate_path = rule_details.get("candidate_path", ["."])
                validator = FolderValidator(
                    catalog, rule_name, candidate_path, error_as_warning
                )
                validators.append(validator)

            elif validator_type == "AzdValidator":
                if not self.args.validate_azd:
                    continue
                infra_yaml_paths = utils.find_infra_yaml_path(self.args.repo_path)
                logging.debug(f"infra_yaml_paths: {infra_yaml_paths}")
                if not infra_yaml_paths:
                    validators.append(
                        AzdValidator(catalog, ".", AzdCommand.UP, error_as_warning)
                    )
                    validators.append(
                        AzdValidator(catalog, ".", AzdCommand.DOWN, error_as_warning)
                    )
                for infra_yaml_path in infra_yaml_paths:
                    validators.append(
                        AzdValidator(
                            catalog, infra_yaml_path, AzdCommand.UP, error_as_warning
                        )
                    )
                    validators.append(
                        AzdValidator(
                            catalog, infra_yaml_path, AzdCommand.DOWN, error_as_warning
                        )
                    )

            # TODO
            # elif validator_type == 'MsdoValidator':
            # validator = MsdoValidator(catalog, ".", rule_name, error_as_warning)

            elif validator_type == "TopicValidator":
                if self.args.expected_topics == "":
                    continue

                topics = rule_details.get("topics", [])
                if self.args.expected_topics:
                    topics = self.args.expected_topics.split(",")
                validator = TopicValidator(
                    catalog, rule_name, topics, self.args.topics, error_as_warning
                )
                validators.append(validator)

            else:
                continue

        logging.info(f"Validators: {[validator.name for validator in validators]}")
        return validators

    def normalize_extensions(self, ext):
        ext_map = {
            '.yml': ['.yml', '.yaml'],
            '.yaml': ['.yml', '.yaml'],
        }
        return ext_map.get(ext.strip(), [ext])
