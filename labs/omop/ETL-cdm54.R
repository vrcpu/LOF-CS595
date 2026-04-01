devtools::install_github("OHDSI/ETL-Synthea")

library(ETLSyntheaBuilder)

cd <- DatabaseConnector::createConnectionDetails(
  dbms     = "postgresql",
  server   = "localhost/omop",
  user     = "postgres",
  password = "admin123",
  port     = 5432,
  pathToDriver = "/Applications/Local Drive/lof-25/LOF-CS595/labs/omop/"  # path to your OMOP folder e.g.
)

cdmSchema = 'cdm54'
cdmVersion     <- "5.4"
resultsDatabaseSchema='results'
vocabFileLoc <- "/Applications/Local Drive/lof-25/LOF-CS595/labs/omop/vocabulary"

ETLSyntheaBuilder::CreateCDMTables(connectionDetails = cd,cdmSchema = cdmSchema,cdmVersion = cdmVersion )

# Note this step assumes you have built the CDM using the ETLSyntheaBuilder::CreateCDMTables command. If you have executed the DDL using the OHDSI/CommonDataModel package you will encounter constraint errors.
ETLSyntheaBuilder::LoadVocabFromCsv(connectionDetails = cd, cdmSchema = cdmSchema, vocabFileLoc = vocabFileLoc,delimiter='\t')
