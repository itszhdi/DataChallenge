import { createContext, useContext } from 'react'

export const DatasetContext = createContext(null)

export const useDataset = () => useContext(DatasetContext)
